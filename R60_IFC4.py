import ifcopenshell
import ifcopenshell.geom
from tabulate import tabulate
from openpyxl import Workbook


def centro_barra(vertices):
    x = [vertices[i] for i in range(0, len(vertices), 3)]
    y = [vertices[i + 1] for i in range(0, len(vertices), 3)]
    z = [vertices[i + 2] for i in range(0, len(vertices), 3)]
    return (sum(x) / len(x), sum(y) / len(y), sum(z) / len(z))


def esta_dentro(ponto, limites):
    return (limites[0] <= ponto[0] <= limites[1] and
            limites[2] <= ponto[1] <= limites[3] and
            limites[4] <= ponto[2] <= limites[5])


# Caminho do IFC
ifc_path = r"C:\Users\jeffe\OneDrive\Documentos\CEFET\MESTRADO\PYTHON\REVIT\UNGROUP_BAR_PADRAO_MEST_RVT25.ifc"
ifc_file = ifcopenshell.open(ifc_path)

# Configuração da geometria
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)
iterator = ifcopenshell.geom.iterator(settings, ifc_file)

# Inicialização
lajes = []
vigas = []
barras_main = []
relatorio = []

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
            elif element.is_a("IfcBeam"):
                vigas.append({'id': element.GlobalId, 'bounds': bounds})
            elif element.is_a("IfcReinforcingBar") and getattr(element, "ObjectType", "") == "MAIN":
                centro = centro_barra(verts)
                diametro = None

                for definition in element.IsDefinedBy:
                    if definition.RelatingPropertyDefinition.is_a("IfcPropertySet"):
                        propset = definition.RelatingPropertyDefinition
                        if propset.Name == "Pset_ReinforcingBarCommon":
                            for prop in propset.HasProperties:
                                if prop.Name == "NominalDiameter":
                                    diametro = prop.NominalValue.wrappedValue / 1000  # mm para metros

                barras_main.append({
                    'id': element.GlobalId,
                    'centro': centro,
                    'diametro': diametro
                })

        if not iterator.next():
            break

# Associação barra-laje e verificação H/8
for barra in barras_main:
    centro = barra['centro']
    diam = barra['diametro']

    if any(esta_dentro(centro, v['bounds']) for v in vigas):
        continue

    for laje in lajes:
        if esta_dentro(centro, laje['bounds']):
            h = laje['bounds'][5] - laje['bounds'][4]  # Zmax - Zmin
            limite = h / 8
            status = "CONFORME COM O ITEM 20.1" if diam < limite else "NÃO CONFORME COM O ITEM 20.1"

            relatorio.append([
                barra['id'],
                laje['id'],
                round(diam * 1000, 2),  # diâmetro em mm
                round(h * 100, 1),      # H em cm
                round(limite * 100, 1),  # limite em cm
                status
            ])
            break

# Imprimir resultado
print(tabulate(relatorio, headers=[
    "ID Barra", "ID Laje", "Diâmetro (mm)", "H da laje (cm)", "H_div_8 (cm)", "Verificação 20.1"
], tablefmt="grid"))

# Exportar para Excel
excel_path = r"C:\Users\jeffe\OneDrive\Documentos\CEFET\MESTRADO\PYTHON\REVIT\verificacao_diametro_h_por_8.xlsx"
wb = Workbook()
ws = wb.active
ws.title = "Verificacao H por 8"

ws.append([
    "ID Barra", "ID Laje", "Diâmetro (mm)", "H da laje (cm)", "H DIV 8(cm)", "Verificação 20.1"
])

for linha in relatorio:
    ws.append(linha)

wb.save(excel_path)
print(f"\nArquivo Excel salvo em: {excel_path}")
