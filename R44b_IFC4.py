import ifcopenshell
import ifcopenshell.geom
from collections import defaultdict
from tabulate import tabulate
import pandas as pd


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
local_file = r"C:\Users\jeffe\OneDrive\Documentos\CEFET\MESTRADO\PYTHON\REVIT\BEAM_UNGROUP_BAR_PADRAO_MEST_RVT25.ifc"
ifc_file = ifcopenshell.open(local_file)

# Configurações da geometria
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)
iterator = ifcopenshell.geom.iterator(settings, ifc_file)

# Listas
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
for barra in barras_main:
    for viga in vigas:
        if esta_dentro_dos_limites(barra['centro'], viga['bounds']):
            associacoes.append({
                'barra_id': barra['id'],
                'centro': barra['centro'],
                'diametro': barra['diametro'],
                'viga_id': viga['id']
            })
            break

# Agrupar barras por viga
barras_por_viga = defaultdict(list)
for assoc in associacoes:
    barras_por_viga[assoc['viga_id']].append(assoc)

# Parâmetros
distancia_minima = 0.02  # 20 mm
agregado_graudo = 0.019
fator_agregado = 0.5 * agregado_graudo
tolerancia_xy = 0.005  # Tolerância para considerar X e Y iguais

distancias_verticais = []

# Verificação vertical
for viga_id, barras in barras_por_viga.items():
    barras_ordenadas = sorted(
        barras, key=lambda b: b['centro'][2])  # ordenadas por Z

    for i, b in enumerate(barras_ordenadas):
        for j in range(i + 1, len(barras_ordenadas)):
            b2 = barras_ordenadas[j]

            x1, y1 = b['centro'][0], b['centro'][1]
            x2, y2 = b2['centro'][0], b2['centro'][1]

            if abs(x1 - x2) <= tolerancia_xy and abs(y1 - y2) <= tolerancia_xy:
                dz = abs(b['centro'][2] - b2['centro'][2])
                diam1 = b['diametro'] if b['diametro'] else 0
                diam2 = b2['diametro'] if b2['diametro'] else 0
                dist_ff = dz - (diam1 + diam2) / 2
                dist_ff_mm = round(dist_ff * 1000, 1)

                maior_diametro = max(diam1, diam2)
                limite_regra44 = max(
                    distancia_minima, fator_agregado, maior_diametro)
                status_regra44 = "OK" if dist_ff >= limite_regra44 else "NÃO OK"

                distancias_verticais.append([
                    b['barra_id'], b2['barra_id'], dist_ff_mm,
                    viga_id, status_regra44
                ])
                break  # só a barra imediatamente acima

# Exibir no terminal
print(tabulate(distancias_verticais, headers=[
    "ID barra 1", "ID barra 2", "Distância FF (mm)", "Viga Associada", "Regra 44"
], tablefmt="grid"))

# Exportar para Excel
caminho_excel = r"C:\Users\jeffe\OneDrive\Documentos\CEFET\MESTRADO\PYTHON\REVIT\verificacao_vertical_regra_44.xlsx"
df_resultados = pd.DataFrame(distancias_verticais, columns=[
    "ID barra 1", "ID barra 2", "Distância FF (mm)", "Viga Associada", "Regra 44"
])
df_resultados.to_excel(caminho_excel, index=False)
print(f"\nArquivo Excel salvo em: {caminho_excel}")
