#REGRA R60
import ifcopenshell
import ifcopenshell.geom
import pandas as pd
from collections import defaultdict

"""
Essa função recebe os vértices das barras de aço e calcular o centro dela.

"""
def centro_barra(vertices):
    x = [vertices[i] for i in range(0, len(vertices), 3)]
    y = [vertices[i + 1] for i in range(0, len(vertices), 3)]
    z = [vertices[i + 2] for i in range(0, len(vertices), 3)]
    return (sum(x) / len(x), sum(y) / len(y), sum(z) / len(z))


"""
Essa função é utilizada para associar uma barra a um elemento elemento estrutural.
Em razão da falha dessa associação no esquema IFC. Atualmente, dentro da comunidade, não se conhece 
um software que consiga exportar essa relação. E ainda, não se sabe ao certo, qual relação seria a correta. 

"""


def verificar_limites(ponto, limites):
    return (limites[0] <= ponto[0] <= limites[1] and
            limites[2] <= ponto[1] <= limites[3] and
            limites[4] <= ponto[2] <= limites[5])


# Caminho do IFC
"""
Função do IfcOpenShell para abrir o arquivo IFC
"""
local_file = r"XXXX"
ifc_file = ifcopenshell.open(local_file)

# Configuração da geometria
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)
iterator = ifcopenshell.geom.iterator(settings, ifc_file)

# Armazenamento de dados

lajes = []
barras_main = []
inconformes_r60 = []

"""
Nesta etapa inicia-se a iteração da geometria e a obtenção de alguns dados
"""
if iterator.initialize():
    while True:
        shape = iterator.get()
        element = ifc_file.by_id(shape.id)

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

            if element.is_a("IfcSlab") and getattr(element, "PredefinedType", "") in ("FLOOR", "ROOF", "BASESLAB"):
                lajes.append({'id': element.GlobalId, 'bounds': bounds})

            elif element.is_a("IfcReinforcingBar") and getattr(element, "ObjectType", "") == "MAIN":
                centro = centro_barra(verts)
                diametro = None

                for definition in element.IsDefinedBy:
                    if definition.RelatingPropertyDefinition.is_a("IfcPropertySet"):
                        propset = definition.RelatingPropertyDefinition
                        if propset.Name == "Pset_ReinforcingBarCommon":
                            for prop in propset.HasProperties:
                                if prop.Name == "NominalDiameter":
                                    diametro = prop.NominalValue.wrappedValue / 1000  # mm para m

                barras_main.append({
                    'id': element.GlobalId,
                    'centro': centro,
                    'diametro': diametro
                })

        if not iterator.next():
            break

# Associar barras às lajes
"""
Laço para associar cada barra a uma laje
"""
barras_por_laje = defaultdict(list)
for barra in barras_main:
    for laje in lajes:
        if verificar_limites(barra['centro'], laje['bounds']):
            barras_por_laje[laje['id']].append(barra)
            break

"""
Inicialização do laço principal de execução
"""
for laje in lajes:
    laje_id = laje['id']
    bounds = laje['bounds']
    h = bounds[5] - bounds[4]  # altura da laje (Zmax - Zmin)
    limite = h / 8

    for barra in barras_por_laje[laje_id]:
        diam = barra['diametro']
        if diam is not None and diam >= limite:
            inconformes_r60.append([
                barra['id'],
                laje_id,
                round(diam * 1000, 2),   # mm
                round(h * 100, 1),       # cm
                round(limite * 100, 1),  # cm
                "NÃO CONFORME COM A REGRA 60"
            ])

# Exportar para Excel (apenas os não conformes)
if inconformes_r60:
    caminho_excel = r"C:/Users/jeffe/OneDrive/Documentos/CEFET/MESTRADO/PYTHON/REVIT/resultado_regra_60.xlsx"
    colunas = ["ID Barra", "ID Laje",
               "Diâmetro (mm)", "H da laje (cm)", "H/8 (cm)", "Verificação regra 60"]

    df_resultado = pd.DataFrame(inconformes_r60, columns=colunas)
    with pd.ExcelWriter(caminho_excel, engine='openpyxl') as writer:
        df_resultado.to_excel(writer, sheet_name="Regra_60_Erros", index=False)

    print(f"\nArquivo Excel salvo em: {caminho_excel}")
else:
    print("\nNenhuma não conformidade encontrada na verificação da regra 60")
