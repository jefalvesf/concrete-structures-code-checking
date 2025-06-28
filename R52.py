#REGRA R52
import ifcopenshell
import ifcopenshell.geom
import numpy as np
import pandas as pd
from collections import defaultdict

# Funções auxiliares

"""
     Calcula Altura, base e comprimento do pilar, assumindo as seguintes premissas:
    Altura é a maior projeção no plano XY.
    Base é a menor projeção no plano XY.
    Comprimento é a variação no eixo Z.
    Para Base e Altura, essa definição pode ser discutida, mas foi a definição que fiz. Pois, na verificação final, 
    isso não fará diferença, ambas as dimensões serão balizadas pela mesma ordem de grandeza 
    """


def calcular_dimensoes(verts):
    vertices = np.array(verts).reshape(-1, 3)
    dim_x = abs(vertices[:, 0].max() - vertices[:, 0].min())
    dim_y = abs(vertices[:, 1].max() - vertices[:, 1].min())
    dim_z = abs(vertices[:, 2].max() - vertices[:, 2].min())
    altura = max(dim_x, dim_y)
    base = min(dim_x, dim_y)
    comprimento = dim_z
    return altura, base, comprimento, dim_x, dim_y


"""
Essa função recebe os vértices das barras de aço e calcular o centro dela.

"""


def centro_barra(vertices):
    x = [vertices[i] for i in range(0, len(vertices), 3)]
    y = [vertices[i+1] for i in range(0, len(vertices), 3)]
    z = [vertices[i+2] for i in range(0, len(vertices), 3)]
    return (sum(x)/len(x), sum(y)/len(y), sum(z)/len(z))


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


# Carregar IFC
"""
Função do IfcOpenShell para abrir o arquivo IFC
"""
local_file = r"XXXX"
ifc_file = ifcopenshell.open(local_file)

# Configurações de geometria
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)
iterator = ifcopenshell.geom.iterator(settings, ifc_file)

# Armazenamento de dados
pilares = []
barras_main = []
associacoes = []
regra_52_erros = []

# Iterar sobre geometria

"""
Inicio da Iteração Pelos elementos
"""

if iterator.initialize():
    while True:
        shape = iterator.get()
        element = ifc_file.by_id(shape.id)
        tipo = element.is_a()

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
            """
            Atribuição das informações de coluna e pset para ReinforcingBar
            """
            if tipo == "IfcColumn":
                pilares.append(
                    {'id': element.GlobalId, 'bounds': bounds, 'verts': verts})
            elif tipo == "IfcReinforcingBar":
                if getattr(element, "ObjectType", "") == "MAIN":
                    centro = centro_barra(verts)
                    diametro = None
                    for definition in element.IsDefinedBy:
                        if definition.RelatingPropertyDefinition.is_a("IfcPropertySet"):
                            pset = definition.RelatingPropertyDefinition
                            if pset.Name == "Pset_ReinforcingBarCommon":
                                for prop in pset.HasProperties:
                                    if prop.Name == "NominalDiameter":
                                        diametro = prop.NominalValue.wrappedValue / 1000  # metros
                    barras_main.append({
                        'id': element.GlobalId,
                        'centro': centro,
                        'diametro': diametro
                    })

        if not iterator.next():
            break

# Associar barras aos pilares
"""
Aqui cria-se uma lista (associações) de dicionários com as associações de barra para cada elemento estrutural.
Se o retorno de verificar_limites é TRUE, o código  executa o append
"""
for barra in barras_main:
    for pilar in pilares:
        if verificar_limites(barra['centro'], pilar['bounds']):
            associacoes.append({
                'barra_id': barra['id'],
                'centro': barra['centro'],
                'diametro': barra['diametro'],
                'pilar_id': pilar['id']
            })
            break

# Agrupar barras por pilar
"""
Aqui agrupa-se as barras por viga.
"""
barras_por_pilar = defaultdict(list)
for assoc in associacoes:
    barras_por_pilar[assoc['pilar_id']].append(assoc)

"""
Inicialização do laço principal de execução
"""
for pilar in pilares:
    gid = pilar['id']
    verts = pilar['verts']
    altura, base, _, dim_x, dim_y = calcular_dimensoes(verts)
    Ac = dim_x * dim_y
    limite_diametro = max(dim_x, dim_y) / 8

    barras = barras_por_pilar.get(gid, [])
    if not barras:
        continue

    total_As = 0
    erro_diametro = False
    erro_area = False
    """
    Verificação do requisito de diâmetro 
    """
    for barra in barras:
        d = barra['diametro']
        if d is not None:
            total_As += (np.pi / 4) * (d ** 2)
            if d < 0.01 or d > limite_diametro:
                erro_area_diametro = True
        else:
           erro_diametro = True  # Ainda registra inconformidade se o diâmetro for indefinido
    """
    Verificação do requisito de taxa de aço em função da área de compressão
    """
    if total_As < 0.004 * Ac or total_As > 0.08 * Ac:
        erro_area = True

    if erro_diametro or erro_area:
        regra_52_erros.append({
            'ID Pilar': gid,
            'Dim X (m)': dim_x,
            'Dim Y (m)': dim_y,
            'Área Pilar (Ac)': Ac,
            'Área de aço (As)': total_As,
            'Qtd Barras': len(barras),
            'Violação Diametro': erro_diametro,
            'Violação Área': erro_area
        })

# Exportar resultados
if regra_52_erros:
    df = pd.DataFrame(regra_52_erros)
    caminho_excel = r"C:/Users/jeffe/OneDrive/Documentos/CEFET/MESTRADO/PYTHON/REVIT/resultado_regra52.xlsx"
    with pd.ExcelWriter(caminho_excel, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Regra52_Erros", index=False)
