#REGRA R44B
import ifcopenshell
import ifcopenshell.geom
from collections import defaultdict
import pandas as pd

"""
Essa função recebe os vértices das barras de aço e calcular o centro dela.
"""
def centro_barra(vertices):
    x_coords = [vertices[i] for i in range(0, len(vertices), 3)]
    y_coords = [vertices[i + 1] for i in range(0, len(vertices), 3)]
    z_coords = [vertices[i + 2] for i in range(0, len(vertices), 3)]
    return (sum(x_coords) / len(x_coords), sum(y_coords) / len(y_coords), sum(z_coords) / len(z_coords))


"""
Essa função é utilizada para associar uma barra a um elemento elemento estrutural.
Em razão da falha dessa associação no esquema IFC. Atualmente, dentro da comunidade, não se conhece 
um software que consiga exportar essa relação. E ainda, não se sabe ao certo, qual relação seria a correta. 
"""
def verificar_limites(ponto, limites):
    return (
        limites[0] <= ponto[0] <= limites[1] and
        limites[2] <= ponto[1] <= limites[3] and
        limites[4] <= ponto[2] <= limites[5]
    )


# Caminho do arquivo IFC
"""
Função do IfcOpenShell para abrir o arquivo IFC
"""
local_file = r"XXXX"
ifc_file = ifcopenshell.open(local_file)

# Configurações da geometria
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)
iterator = ifcopenshell.geom.iterator(settings, ifc_file)

# Parâmetros balizadores e  variáveis para armazenar dados e resultados

vigas = []
barras_main = []
associacoes = []
distancias_verticais = []
distancia_minima = 0.02  # 20 mm
agregado_graudo = 0.019
fator_agregado = 0.5 * agregado_graudo
tolerancia_xy = 0.005  # Tolerância para considerar X e Y iguais

"""
Etapa de processamento da geometria.
Recurso que processa uma grande quantidade de geometria com melhor desempenho e exigindo menos da máquina. 
Neste caso, além de salvar o globalID da viga e das barras de aço, e o centro da barra de aço. 
Também é necessária a informação do Diametro dentro do Pset especifico para ele.
"""

if iterator.initialize():
    while True:
        shape = iterator.get()
        element = ifc_file.by_id(shape.id)
        element_type = element.is_a()

        try:
            verts = shape.geometry.verts
        except AttributeError:
            verts = []

        if verts:
            bounds = (
                min(verts[0::3]), max(verts[0::3]),
                min(verts[1::3]), max(verts[1::3]),
                min(verts[2::3]), max(verts[2::3])
            )

            if element_type == "IfcBeam":
                vigas.append({'id': element.GlobalId, 'bounds': bounds})
            elif element_type == "IfcReinforcingBar":
                if getattr(element, "ObjectType", "") == "MAIN":
                    centro = centro_barra(verts)
                    diameter = None
                    for definition in element.IsDefinedBy:
                        if definition.RelatingPropertyDefinition.is_a("IfcPropertySet"):
                            prop_set = definition.RelatingPropertyDefinition
                            if prop_set.Name == "Pset_ReinforcingBarCommon":
                                for prop in prop_set.HasProperties:
                                    if prop.Name == "NominalDiameter":
                                        diameter = prop.NominalValue.wrappedValue / 1000
                    barras_main.append({
                        'id': element.GlobalId,
                        'centro': centro,
                        'diametro': diameter
                    })

        if not iterator.next():
            break

# Associar barras às vigas
"""
Aqui cria-se uma lista de dicionários com as associações de barra para cada elemento estrutural.
De modo a garantir que uma barra esteja somente em um elemento estrutural. 
"""
for barra in barras_main:
    for viga in vigas:
        if verificar_limites(barra['centro'], viga['bounds']):
            associacoes.append({
                'barra_id': barra['id'],
                'centro': barra['centro'],
                'diametro': barra['diametro'],
                'viga_id': viga['id']
            })
            break

# Agrupar barras por viga
"""
Aqui agrupa-se as barras por viga.
"""
barras_por_viga = defaultdict(list)
for assoc in associacoes:
    barras_por_viga[assoc['viga_id']].append(assoc)


# Verificação vertical
"""
Inicia-se a verificação por viga, ordenando  barras por Z. Ou seja, para que a barra seja verificada apenas com a imediatamente acima.
"""
for viga_id, barras in barras_por_viga.items():
    # Ordenar as barras da viga pela coordenada Z (altura)
    barras_ordenadas = sorted(barras, key=lambda b: b['centro'][2])

    # Percorrer cada barra usando o índice i
    for i in range(len(barras_ordenadas)):
        b = barras_ordenadas[i]  # barra na posição i

        """Comparar com todas as barras acima dela na lista (índices maiores que i)"""
        for j in range(i + 1, len(barras_ordenadas)):
            b2 = barras_ordenadas[j]  # barra na posição j

            x1, y1 = b['centro'][0], b['centro'][1]
            x2, y2 = b2['centro'][0], b2['centro'][1]

            # Só compara se estiverem alinhadas no plano XY
            if abs(x1 - x2) <= tolerancia_xy and abs(y1 - y2) <= tolerancia_xy:
                dz = abs(b['centro'][2] - b2['centro'][2])  # diferença em Z (altura)
                diam1 = b['diametro'] if b['diametro'] else 0
                diam2 = b2['diametro'] if b2['diametro'] else 0
                dist_ff = dz - (diam1 + diam2) / 2
                dist_ff_mm = round(dist_ff * 1000, 1)

                maior_diametro = max(diam1, diam2)
                limite_regra44b = max(distancia_minima, fator_agregado, maior_diametro)
                status_regra44b = "OK" if dist_ff >= limite_regra44b else "NÃO OK"

                distancias_verticais.append([
                    b['barra_id'], b2['barra_id'],
                    dist_ff_mm, viga_id, status_regra44b
                ])
                break  # só compara com a primeira barra logo acima (mais próxima)

# Filtrar apenas os resultados que não atendem à Regra 44
inconformes = [linha for linha in distancias_verticais if linha[4] == "NÃO OK"]


# Salvar os resultados inconformes em uma planilha Excel
if inconformes:
    caminho_arquivo = r"C:/Users/jeffe/OneDrive/Documentos/CEFET/MESTRADO/PYTHON/REVIT/resultado_regra44b.xlsx"
    colunas = ["ID barra 1", "ID barra 2",
               "DistânciaFF (mm)", "Viga Associada", "Regra 44"]
    df_inconformes = pd.DataFrame(inconformes, columns=colunas)

    with pd.ExcelWriter(caminho_arquivo, engine='openpyxl') as writer:
        df_inconformes.to_excel(
            writer, sheet_name="Inconformidades", index=False)
