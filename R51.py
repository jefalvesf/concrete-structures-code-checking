#REGRA R51
import ifcopenshell
import ifcopenshell.geom
import numpy as np
import pandas as pd

# Função para calcular as dimensões com base nos vértices


def calcular_dimensoes(verts):
    """
    Calcula Altura, base e comprimento do pilar, assumindo as seguintes premissas:
    Altura é a maior projeção no plano XY.
    Base é a menor projeção no plano XY.
    Comprimento é a variação no eixo Z.
    Para Base e Altura, essa definição pode ser discutida, mas foi a definição que fiz. Pois, na verificação final, 
    isso não fará diferença, ambas as dimensões serão balizadas pela mesma ordem de grandeza 
    """

    vertices = np.array(verts).reshape(-1, 3)

    # Dimensões no espaço
    dim_x = abs(vertices[:, 0].max() - vertices[:, 0].min())  # Variação em X
    dim_y = abs(vertices[:, 1].max() - vertices[:, 1].min())  # Variação em Y
    dim_z = abs(vertices[:, 2].max() - vertices[:, 2].min())  # Variação em Z

    # Comprimento (maior dimensão no plano XY)
    altura = max(dim_x, dim_y)

    # Largura (menor dimensão no plano XY)
    base = min(dim_x, dim_y)

    # Altura (variação no eixo Z)
    comprimento = dim_z

    return altura, base, comprimento, dim_x, dim_y


# Carregar o arquivo IFC
"""
Função do IfcOpenShell para abrir o arquivo IFC
"""
local_file = r"XXXX"
ifc_file = ifcopenshell.open(local_file)

# Configurações de geometria
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)


# Inicializar variáveis para armazenar resultados
columns = ifc_file.by_type("IfcColumn")
column_dimensions = []
all_not_verified = []
regra_51_erros = []

# Iterar pelos pilares no modelo

"""
Inicio da Iteração Pelos elementos
"""
for column in columns:
    try:
        # Criar a geometria do pilar
        shape = ifcopenshell.geom.create_shape(settings, column)
        verts = shape.geometry.verts

        # Calcular dimensões do pilar
        altura, base, comprimento, dim_x, dim_y = calcular_dimensoes(
            verts)

        # Verificação da regra 51: maior dimensão (X ou Y) não pode ser maior que 5x a menor
        max_dim = max(dim_x, dim_y)
        min_dim = min(dim_x, dim_y)

        if max_dim > 5 * min_dim:
            regra_51_erros.append(column.GlobalId)

        # Armazenar o ID e as dimensões do pilar
        column_dimensions.append(
            (column.GlobalId, dim_x, dim_y, comprimento, max_dim, min_dim, regra_51_erros))

    except Exception as e:
        # Caso ocorra algum erro, adicionar à lista de não verificáveis
        all_not_verified.append(column.GlobalId)

# Filtrar apenas os pilares que violam a Regra 51
inconformes_regra51 = [
    (gid, dx, dy, comp, maxd, mind)
    for (gid, dx, dy, comp, maxd, mind, erros) in column_dimensions
    if gid in regra_51_erros
]

# Salvar os resultados inconformes em uma planilha Excel
if inconformes_regra51:
    caminho_excel = r"C:/Users/jeffe/OneDrive/Documentos/CEFET/MESTRADO/PYTHON/REVIT/resultado_regra51.xlsx"
    colunas = ["ID Pilar", "Dim X (m)", "Dim Y (m)",
               "Comprimento (m)", "Maior Dimensão", "Menor Dimensão"]
    df_erros = pd.DataFrame(inconformes_regra51, columns=colunas)

    with pd.ExcelWriter(caminho_excel, engine='openpyxl') as writer:
        df_erros.to_excel(writer, sheet_name="Regra51_Erros", index=False)
