#REGRA R44A

import ifcopenshell
import ifcopenshell.geom
import pandas as pd
from collections import defaultdict

# Função para calcular o centro da barra de aço


"""
Essa função recebe os vértices das barras de aço e calcular o centro dela.

"""


def centro_barra(vertices):
    x_coords = [vertices[i] for i in range(0, len(vertices), 3)]
    y_coords = [vertices[i + 1] for i in range(0, len(vertices), 3)]
    z_coords = [vertices[i + 2] for i in range(0, len(vertices), 3)]
    return (sum(x_coords) / len(x_coords), sum(y_coords) / len(y_coords), sum(z_coords) / len(z_coords))

# Função para verificar se a barra está dentro da viga


"""
Essa função é utilizada para associar uma barra a um elemento elemento estrutural.
Em razão da falha dessa associação no esquema IFC. Atualmente, dentro da comunidade, não se conhece 
um software que consiga exportar essa relação. E ainda, não se sabe ao certo, qual relação seria a correta. 

"""


def verificar_limites(bar_centro, limites_elemento):
    return (
        limites_elemento[0] <= bar_centro[0] <= limites_elemento[1] and
        limites_elemento[2] <= bar_centro[1] <= limites_elemento[3] and
        limites_elemento[4] <= bar_centro[2] <= limites_elemento[5]
    )


"""
Função do IfcOpenShell para abrir o arquivo IFC
"""
# Caminho do arquivo IFC
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
distancias = []
distancia_minima = 0.02  # 20 mm
agregado_graudo = 0.019
fator_agregado = 1.2 * agregado_graudo
tolerancia_z = 0.005  # 5 mm


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


# Análise por viga

"""
Inicia-se a verificação por viga, agrupando barras na mesma altura em Z. Ou seja, essas barras serão verificadas a distância
horizontal. De modo a garantir que barras em posições diferentes em Z na viga, sejam verificadas horizontalmente. 
"""
for viga_id, barras in barras_por_viga.items():
    # Agrupar por camada Z
    camadas = defaultdict(list)
    for barra in barras:
        z = barra['centro'][2]
        grupo_encontrado = False
        for key in camadas:
            if abs(z - key) <= tolerancia_z:
                camadas[key].append(barra)
                grupo_encontrado = True
                break
        if not grupo_encontrado:
            camadas[z].append(barra)
    """
    Para cada barra no grupo de camadas, ele ordenad ela no eixo X, para que a verificação da distância ocorra apenas entre barras vizinhas
    """
    for camada_z, grupo_barras in camadas.items():
        grupo_ordenado = sorted(
            grupo_barras, key=lambda b: b['centro'][0])  # ordenar por X
        """
        Inicia-se a verificação pegando duas barras na posição i e na posição i+1, calcula-se o cnetro delas
        e as distâncias entre elas
        """
        for i in range(len(grupo_ordenado) - 1):
            b = grupo_ordenado[i]
            b2 = grupo_ordenado[i + 1]

            x1, y1 = b['centro'][0], b['centro'][1]
            x2, y2 = b2['centro'][0], b2['centro'][1]
            dx = abs(x1 - x2)
            dy = abs(y1 - y2)
            dist_cc_m = dx if dx > dy else dy
            """
            Item de segurança para que não sejam verificadas barras longe demais, para que não polua o código
            """
            if dist_cc_m > 1.0:
                continue
            """
            A norma determina que a distância minima seja calculada de face a face, então essa parte do código 
            ajusta as distâncias considerando de face a face.
            """
            diam1 = b['diametro'] if b['diametro'] else 0
            diam2 = b2['diametro'] if b2['diametro'] else 0
            dist_ff_m = dist_cc_m - (diam1 + diam2) / 2

            dist_ff_mm = round(dist_ff_m * 1000, 1)
            """
            Nesta etapa é realizada a verificação dos critérios normativos. 
            """
            maior_diametro_m = max(diam1, diam2)
            limite_regra44_m = round(
                max(distancia_minima, fator_agregado, maior_diametro_m), 3)
            status_regra44a = "OK" if dist_ff_m >= limite_regra44_m else "NÃO OK"

            distancias.append([
                b['barra_id'], b2['barra_id'],
                dist_ff_mm, viga_id, status_regra44a
            ])

# Imprimir resultado no excel

# Filtrar apenas os resultados que não atendem à Regra 44
inconformes = [linha for linha in distancias if linha[4] == "NÃO OK"]

# Salvar os resultados inconformes em uma planilha Excel
if inconformes:
    caminho_arquivo = r"C:/Users/jeffe/OneDrive/Documentos/CEFET/MESTRADO/PYTHON/REVIT/resultado_regra44a.xlsx"
    colunas = ["ID barra 1", "ID barra 2",
               "DistânciaFF (mm)", "Viga Associada", "Regra 44"]
    df_inconformes = pd.DataFrame(inconformes, columns=colunas)

    with pd.ExcelWriter(caminho_arquivo, engine='openpyxl') as writer:
        df_inconformes.to_excel(
            writer, sheet_name="Inconformidades", index=False)
