import ifcopenshell
import ifcopenshell.geom
import math
from tabulate import tabulate
from openpyxl import Workbook


def centro_barra(vertices):
    x_coords = [vertices[i] for i in range(0, len(vertices), 3)]
    y_coords = [vertices[i + 1] for i in range(0, len(vertices), 3)]
    z_coords = [vertices[i + 2] for i in range(0, len(vertices), 3)]
    return (sum(x_coords) / len(x_coords), sum(y_coords) / len(y_coords), sum(z_coords) / len(z_coords))


def esta_dentro_dos_limites(ponto, limites):
    return (
        limites[0] <= ponto[0] <= limites[1] and
        limites[2] <= ponto[1] <= limites[3] and
        limites[4] <= ponto[2] <= limites[5]
    )


# Caminho do arquivo IFC
local_file = r"C:\Users\jeffe\OneDrive\Documentos\CEFET\MESTRADO\PYTHON\REVIT\UNGROUP_BAR_PADRAO_MEST_RVT25.ifc"
ifc_file = ifcopenshell.open(local_file)

# Configurações da geometria
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)
iterator = ifcopenshell.geom.iterator(settings, ifc_file)

# Listas
lajes = []
vigas = []
barras_main = []
associacoes = []

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

            if element_type == "IfcSlab":
                predefined = getattr(element, "PredefinedType", None)
                if predefined in ("FLOOR", "ROOF", "BASESLAB"):
                    lajes.append(
                        {'id': element.GlobalId, 'bounds': bounds, 'tipo': predefined})
            elif element_type == "IfcBeam":
                vigas.append({'id': element.GlobalId, 'bounds': bounds})
            elif element_type == "IfcReinforcingBar":
                if getattr(element, "ObjectType", "") == "MAIN":
                    centro = centro_barra(verts)

                    # Buscar o diâmetro nominal (em mm) e converter para metros
                    diameter = None
                    for definition in element.IsDefinedBy:
                        if definition.RelatingPropertyDefinition.is_a("IfcPropertySet"):
                            prop_set = definition.RelatingPropertyDefinition
                            if prop_set.Name == "Pset_ReinforcingBarCommon":
                                for prop in prop_set.HasProperties:
                                    if prop.Name == "NominalDiameter":
                                        diameter = prop.NominalValue.wrappedValue / 1000  # mm para metros

                    barras_main.append(
                        {'id': element.GlobalId, 'centro': centro, 'diametro': diameter})

        if not iterator.next():
            break

# Verificar se cada barra está dentro de alguma laje (e não dentro de viga)
for barra in barras_main:
    dentro_de_viga = any(esta_dentro_dos_limites(
        barra['centro'], viga['bounds']) for viga in vigas)
    if dentro_de_viga:
        continue

    for laje in lajes:
        if esta_dentro_dos_limites(barra['centro'], laje['bounds']):
            associacoes.append({
                'barra_id': barra['id'],
                'centro': barra['centro'],
                'diametro': barra['diametro'],
                'laje_id': laje['id'],
                'tipo_laje': laje['tipo']
            })
            break

# Calcular distâncias entre barras consecutivas (mesma laje)
distancias = []
for i in range(len(associacoes) - 1):
    b1 = associacoes[i]
    b2 = associacoes[i + 1]

    if b1['laje_id'] != b2['laje_id']:
        continue

    x1, y1 = b1['centro'][0], b1['centro'][1]
    x2, y2 = b2['centro'][0], b2['centro'][1]
    dx = abs(x1 - x2)
    dy = abs(y1 - y2)

    if dx > dy:
        pos1 = round(x1, 3)
        pos2 = round(x2, 3)
        dist_cc = round(dx, 3)
    else:
        pos1 = round(y1, 3)
        pos2 = round(y2, 3)
        dist_cc = round(dy, 3)

    if dist_cc > 1.0:
        continue

    diam1 = b1['diametro'] if b1['diametro'] else 0
    diam2 = b2['diametro'] if b2['diametro'] else 0
    dist_ff = round(dist_cc - (diam1 + diam2) / 2, 3)

    # Verificação da Regra 20.1 da NBR 6118:2023
    espessura_laje = 0
    for laje in lajes:
        if laje['id'] == b1['laje_id']:
            espessura_laje = laje['bounds'][5] - laje['bounds'][4]
            break

    limite_20_1 = None
    if diam1 >= 0.02 or diam2 >= 0.02:
        limite_20_1 = 15 * max(diam1, diam2)
    else:
        limite_20_1 = min(2 * espessura_laje, 0.20)

    verifica_20_1 = "OK" if dist_ff <= limite_20_1 else "NÃO CONFORME"

    tipo_laje = b1['tipo_laje']
    identificador = f"{b1['laje_id']} ({tipo_laje})"

    distancias.append([
        b1['barra_id'], b2['barra_id'],
        pos1, pos2,
        dist_cc, dist_ff,
        identificador, verifica_20_1
    ])

# Exibir resultado no terminal
print(tabulate(distancias, headers=[
    "ID barra 1", "ID barra 2", "Posição barra 1",
    "Posição barra 2", "DistânciaCC", "DistânciaFF", "Elemento estrutural associado",
    "Verificação NBR 6118 (20.1)"
], tablefmt="grid"))

# Exportar para Excel
caminho_excel = r"C:\Users\jeffe\OneDrive\Documentos\CEFET\MESTRADO\PYTHON\REVIT\distancia_entre_barras_com_posicoes.xlsx"
wb = Workbook()
ws = wb.active
ws.title = "Distâncias Detalhadas"

ws.append([
    "ID barra 1", "ID barra 2", "Posição barra 1",
    "Posição barra 2", "DistânciaCC", "DistânciaFF", "Elemento estrutural associado",
    "Verificação NBR 6118 (20.1)"
])

for linha in distancias:
    ws.append(linha)

wb.save(caminho_excel)
print(f"\nArquivo Excel salvo em: {caminho_excel}")
