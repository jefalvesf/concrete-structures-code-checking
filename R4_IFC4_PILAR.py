import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import math
from tabulate import tabulate

# Função para calcular a distância entre dois pontos 3D


def distancia(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)

# Função para calcular o centro de uma barra


def centro_barra(vertices):
    x_coords = [vertices[i] for i in range(0, len(vertices), 3)]
    y_coords = [vertices[i + 1] for i in range(0, len(vertices), 3)]
    z_coords = [vertices[i + 2] for i in range(0, len(vertices), 3)]
    return (sum(x_coords) / len(x_coords), sum(y_coords) / len(y_coords), sum(z_coords) / len(z_coords))

# Função para calcular o Valor ALFA (extremidade da barra LIGATURE)


def calcular_valor_alfa(coord_barra, diametro_ligature, diametro_main):
    distancia = (diametro_main / 2) + diametro_ligature
    alfa_x_1 = coord_barra[0] - distancia  # subtraindo a distância
    alfa_y_1 = coord_barra[1] - distancia  # subtraindo a distância
    alfa_x_2 = coord_barra[0] + distancia  # somando a distância
    alfa_y_2 = coord_barra[1] + distancia  # somando a distância
    return (alfa_x_1, alfa_y_1), (alfa_x_2, alfa_y_2)

# Função para calcular o cobrimento


def calcular_cobrimento(alfa_x, alfa_y, bounds_elemento):
    xmin, xmax, ymin, ymax = bounds_elemento[0], bounds_elemento[1], bounds_elemento[2], bounds_elemento[3]
    diferenca_x = [abs(alfa_x - xmin), abs(alfa_x - xmax)]
    diferenca_y = [abs(alfa_y - ymin), abs(alfa_y - ymax)]
    return min(min(diferenca_x), min(diferenca_y)), diferenca_x, diferenca_y

# Função para verificar se uma barra está dentro dos limites de um elemento estrutural


def esta_dentro_dos_limites(bar_centro, bounds_elemento):
    return (
        bounds_elemento[0] <= bar_centro[0] <= bounds_elemento[1] and
        bounds_elemento[2] <= bar_centro[1] <= bounds_elemento[3] and
        bounds_elemento[4] <= bar_centro[2] <= bounds_elemento[5]
    )

# Função para depuração


def depuracao_barra(barra_id, tipo_barra, centro_barra, diametro_barra, diametro_ligadura, bounds_elemento, ponto_alfa, diferencas_x, diferencas_y, cobrimento):
    print(f"\nDepuração para a barra {tipo_barra}: {barra_id}")
    print(f"Coordenadas da barra (centro): {centro_barra}")
    print(f"Diâmetro da ligadura (m): {diametro_ligadura:.6f}")
    print(f"Diâmetro da barra principal (m): {diametro_barra:.6f}")
    print(f"Valor ALFA (X, Y): {ponto_alfa}")
    print(f"Limites do elemento estrutural: {bounds_elemento}")
    print(f"Diferenças em X: {diferencas_x}")
    print(f"Diferenças em Y: {diferencas_y}")
    print(f"Cobrimento calculado: {cobrimento}")


# Abrir o arquivo IFC
local_file = r"C:/Users/jeffe/Downloads/RELATIONSHIP_RVT25.ifc"
try:
    ifc_file = ifcopenshell.open(local_file)
except Exception as e:
    print(f"Erro ao abrir o arquivo IFC: {e}")
    raise e

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

iterator = ifcopenshell.geom.iterator(settings, ifc_file)
pilares = []
barras_main = []
barras_ligature = []
resultados = []

diametro_ligature_m = None

if iterator.initialize():
    while True:
        shape = iterator.get()
        element = ifc_file.by_id(shape.id)
        element_type = element.is_a()

        try:
            verts = shape.geometry.verts
        except AttributeError:
            print(f"Aviso: O elemento {element.GlobalId} ({
                  element_type}) possui representação geométrica não suportada.")
            verts = []

        if verts:
            bounds = (
                min(verts[0::3]), max(verts[0::3]),
                min(verts[1::3]), max(verts[1::3]),
                min(verts[2::3]), max(verts[2::3])
            )

            if element_type == "IfcColumn":
                pilares.append({'id': element.GlobalId, 'bounds': bounds})
            elif element_type == "IfcReinforcingBar":
                object_type = getattr(element, "ObjectType", "")
                if object_type == "MAIN":
                    barras_main.append({'id': element.GlobalId, 'bounds': bounds, 'centro': centro_barra(
                        verts), 'element': element})
                elif object_type == "LIGATURE":
                    barras_ligature.append(
                        {'id': element.GlobalId, 'bounds': bounds, 'centro': centro_barra(verts), 'element': element})

        if not iterator.next():
            break

for barra_main in barras_main:
    barra_main_centro = barra_main['centro']
    barra_main_element = barra_main['element']
    psets = ifcopenshell.util.element.get_psets(barra_main_element)
    diametro_main = psets.get("Pset_ReinforcingBarCommon", {}).get(
        "NominalDiameter", None)

    if diametro_main is None or diametro_main <= 0:
        continue

    diametro_main_m = diametro_main * 0.001

    for pilar in pilares:
        if esta_dentro_dos_limites(barra_main_centro, pilar['bounds']):
            for barra_ligature in barras_ligature:
                if esta_dentro_dos_limites(barra_ligature['centro'], pilar['bounds']):
                    psets_ligature = ifcopenshell.util.element.get_psets(
                        barra_ligature['element'])
                    diametro_ligature = psets_ligature.get(
                        "Pset_ReinforcingBarCommon", {}).get("NominalDiameter", None)

                    if diametro_ligature is None or diametro_ligature <= 0:
                        continue

                    diametro_ligature_m = diametro_ligature * 0.001
                    alfa_1, alfa_2 = calcular_valor_alfa(
                        barra_main_centro, diametro_ligature_m, diametro_main_m)

                    # Calculando o cobrimento para os quatro valores de alfa
                    cobrimento_1, diferencas_x_1, diferencas_y_1 = calcular_cobrimento(
                        alfa_1[0], alfa_1[1], pilar['bounds'])
                    cobrimento_2, diferencas_x_2, diferencas_y_2 = calcular_cobrimento(
                        alfa_2[0], alfa_2[1], pilar['bounds'])

                    # Calculando para os outros dois valores alfa_x_2, alfa_y_1, e alfa_y_2
                    cobrimento_3, diferencas_x_3, diferencas_y_3 = calcular_cobrimento(
                        alfa_1[0], alfa_2[1], pilar['bounds'])
                    cobrimento_4, diferencas_x_4, diferencas_y_4 = calcular_cobrimento(
                        alfa_2[0], alfa_1[1], pilar['bounds'])

                    # Selecionando o menor valor de cobrimento
                    cobrimento = min(cobrimento_1, cobrimento_2,
                                     cobrimento_3, cobrimento_4)

                    # Verificando se o cobrimento é adequado
                    cobrimento_adequado = "Adequado" if cobrimento + \
                        0.01 > diametro_main_m else "Inadequado"

                    # Depuração
                    depuracao_barra(barra_main['id'], "MAIN", barra_main_centro, diametro_main_m,
                                    diametro_ligature_m, pilar['bounds'], alfa_1, diferencas_x_1, diferencas_y_1, cobrimento_1)
                    depuracao_barra(barra_main['id'], "MAIN", barra_main_centro, diametro_main_m,
                                    diametro_ligature_m, pilar['bounds'], alfa_2, diferencas_x_2, diferencas_y_2, cobrimento_2)

                    # Armazenando o resultado
                    resultados.append(
                        [barra_main['id'], f"{cobrimento:.6f}", cobrimento_adequado])

# Exibindo os resultados
print(tabulate(resultados, headers=[
      "Barra MAIN ID", "Cobrimento (m)", "Adequação"], tablefmt="grid", floatfmt=".6f"))
