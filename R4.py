#REGRA R4
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import math
import pandas as pd
from tabulate import tabulate


# Função que calcula o centro da barra de aço

"""
Essa função recebe os vértices das barras de aço e calcular o centro dela
Ponto importante é que a depender da regra, talvez seja interessante calcular o centro apenas da seção
desconsiderando o Z. 

"""


def centro_barra(vertices):
    x_coords = [vertices[i] for i in range(0, len(vertices), 3)]
    y_coords = [vertices[i + 1] for i in range(0, len(vertices), 3)]
    z_coords = [vertices[i + 2] for i in range(0, len(vertices), 3)]
    return (sum(x_coords) / len(x_coords), sum(y_coords) / len(y_coords), sum(z_coords) / len(z_coords))

# Função para calcular o Valor ALFA (extremidade da barra LIGATURE)


"""
Foi denominado como valor Alfa a posição das extremidades das barras de aço que serão utilizadas para calcular o cobrimnto.
Isso aconteceu porque deve-se considerar a extremidade da barra de estribo que envolve a barra longitudinal, 
para se calcular o cobrimento. Além disso, a face do elemento estrutrual mais proxima da barra longituinal varia em função 
da sua posição, então pode-se haver 4 diferentes distâncias, a depender da sua próximidade com a extremidade. 

"""


def calcular_valor_alfa(coord_barra, diametro_ligature, diametro_main):
    distancia = (diametro_main / 2) + diametro_ligature
    alfa_x_1 = coord_barra[0] - distancia
    alfa_y_1 = coord_barra[1] - distancia
    alfa_x_2 = coord_barra[0] + distancia
    alfa_y_2 = coord_barra[1] + distancia
    return (alfa_x_1, alfa_y_1), (alfa_x_2, alfa_y_2)

# Função para calcular o cobrimento


"""
Essa função recebe a posição mais externa das barras de aço, e os limites do elemento estrutural.
Esses valores de coordenadas serão utilizados para calcular o cobrimento projetado no elemento.

"""


def calcular_cobrimento(alfa_x, alfa_y, limites_elemento):
    xmin, xmax, ymin, ymax = limites_elemento[0], limites_elemento[1], limites_elemento[2], limites_elemento[3]
    diferenca_x = [abs(alfa_x - xmin), abs(alfa_x - xmax)]
    diferenca_y = [abs(alfa_y - ymin), abs(alfa_y - ymax)]
    return min(min(diferenca_x), min(diferenca_y)), diferenca_x, diferenca_y

# Verifica se a barra está dentro dos limites do elemento estrutural


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
local_file = r"XXXX"
ifc_file = ifcopenshell.open(local_file)


# Configurações de geometria
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

# Inicializar variáveis para armazenar dados e resultados

iterator = ifcopenshell.geom.iterator(settings, ifc_file)
pilares = []
barras_main = []
barras_ligature = []
resultados = []
nao_atendeu_regra_4 = []

"""
Etapa de processamento da geometria.
Recurso que processa uma grande quantidade de geometria com melhor desempenho e exigindo menos da máquina. 
Nesta etapa, além de processar a geometria, são obtidas e aramazenadas as informações de: 
    Pilares: Vértices e GlobalIDs
    Brras de aço: ObjectType, Psets, Vértices e GlobalIDs

"""
if iterator.initialize():
    while True:
        shape = iterator.get()
        element = ifc_file.by_id(shape.id)
        """Acima o código busca o elemento por completo noa arquivo ifc a partir do id da geom processada """
        element_type = element.is_a()
        """Salvando a classe daquele elemento"""
        try:
            verts = shape.geometry.verts
        except AttributeError:
            verts = []

        if verts:
            limites = (
                min(verts[0::3]), max(verts[0::3]),
                min(verts[1::3]), max(verts[1::3]),
                min(verts[2::3]), max(verts[2::3])
            )

            if element_type == "IfcColumn":
                pilares.append({'id': element.GlobalId, 'limites': limites})
            elif element_type == "IfcReinforcingBar":
                object_type = getattr(element, "ObjectType", "")
                if object_type == "MAIN":
                    barras_main.append({'id': element.GlobalId, 'limites': limites, 'centro': centro_barra(
                        verts), 'element': element})
                elif object_type == "LIGATURE":
                    barras_ligature.append(
                        {'id': element.GlobalId, 'limites': limites, 'centro': centro_barra(verts), 'element': element})

        if not iterator.next():
            break

"""
Essa etapa consiste em, primeiramente, atribuar à variáveis as informações processadas no iterador. 
Segundo, são realizadas as associações das barras de aço aos elementos estruturais, além de 
chamar as funções que realizam os calculos de alfa e cobrimento. Por fim, ainda nesse loop é salvo 
se a barra de aço está com o cobrimento adequado seguindo o item da normativa brasileira NBR 6118. 

"""
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
        if verificar_limites(barra_main_centro, pilar['limites']):
            for barra_ligature in barras_ligature:
                if verificar_limites(barra_ligature['centro'], pilar['limites']):
                    psets_ligature = ifcopenshell.util.element.get_psets(
                        barra_ligature['element'])
                    diametro_ligature = psets_ligature.get(
                        "Pset_ReinforcingBarCommon", {}).get("NominalDiameter", None)

                    if diametro_ligature is None or diametro_ligature <= 0:
                        continue

                    diametro_ligature_m = diametro_ligature * 0.001
                    alfa_1, alfa_2 = calcular_valor_alfa(
                        barra_main_centro, diametro_ligature_m, diametro_main_m)

                    cobrimento_1, _, _ = calcular_cobrimento(
                        alfa_1[0], alfa_1[1], pilar['limites'])
                    cobrimento_2, _, _ = calcular_cobrimento(
                        alfa_2[0], alfa_2[1], pilar['limites'])
                    cobrimento_3, _, _ = calcular_cobrimento(
                        alfa_1[0], alfa_2[1], pilar['limites'])
                    cobrimento_4, _, _ = calcular_cobrimento(
                        alfa_2[0], alfa_1[1], pilar['limites'])

                    cobrimento = min(cobrimento_1, cobrimento_2,
                                     cobrimento_3, cobrimento_4)

                    cobrimento_adequado = "Atende a Regra 4" if cobrimento - \
                        0.01 > diametro_main_m else "Não Atende a Regra 4"

                    resultados.append(
                        [barra_main['id'], f"{cobrimento:.6f}", cobrimento_adequado])

                    if cobrimento_adequado == "Não Atende a Regra 4":
                        nao_atendeu_regra_4.append({
                            "ID_Barra_MAIN": barra_main['id'],
                            "ID_Pilar_Associado": pilar['id'],
                            "Status": "Não Atendeu a Regra 4"
                        })


"""
Resultados no Console para verificação 
"""
print(tabulate(resultados, headers=[
      "Barra MAIN ID", "Cobrimento (m)", "Adequação"], tablefmt="grid", floatfmt=".6f"))

# Exportando para Excel

"""
Parte do processo de code checking, exportando os resultados para um relatório, neste caso, em Excel. 

"""
df = pd.DataFrame(nao_atendeu_regra_4)
caminho_excel = r"C:/Users/jeffe/OneDrive/Documentos/CEFET/MESTRADO/PYTHON/REVIT/resultado_regra4.xlsx"
df.to_excel(caminho_excel, index=False)
print(f"\nExportado para: {caminho_excel}")
