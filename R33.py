#REGRA R33
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
    dim_x = vertices[:, 0].max() - vertices[:, 0].min()  # Variação em X
    dim_y = vertices[:, 1].max() - vertices[:, 1].min()  # Variação em Y
    dim_z = vertices[:, 2].max() - vertices[:, 2].min()  # Variação em Z

    # Altura da seção (maior dimensão no plano XY)
    altura = max(dim_x, dim_y)

    # Base da seção (menor dimensão no plano XY)
    base = min(dim_x, dim_y)

    # Comprimento do Pilar (variação no eixo Z)
    comprimento = dim_z

    return base, altura, comprimento


"""
Função do IfcOpenShell para abrir o arquivo IFC
"""
# Carregar o arquivo IFC
local_file = r"XXXX"
ifc_file = ifcopenshell.open(local_file)

# Configurações de geometria
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

# Inicializar variáveis para armazenar resultados
columns = ifc_file.by_type("IfcColumn")
column_dimensions = []
all_issues = []
all_not_verified = []

# Iterar pelos pilares no modelo
for column in columns:
    try:
        # Criar a geometria do pilar
        """
        Nesta etapa-se inicia-se o processamento da geometria.
        """
        shape = ifcopenshell.geom.create_shape(settings, column)
        verts = shape.geometry.verts

        # Calcular dimensões do pilar
        """
        Nesta etapa, passas-se os vértices e chama-se a função para calcular dimensões
        """
        base, altura, comprimento = calcular_dimensoes(verts)

        # Verificação da largura e altura
        if base < 0.19 or altura < 0.19:  # Se a largura ou a comprimento for menor que 19 cm
            all_issues.append(column.GlobalId)

        # Armazenar o ID e as dimensões do pilar
        column_dimensions.append((column.GlobalId, base, altura, comprimento))

    except Exception as e:
        # Caso ocorra algum erro, adicionar à lista de não verificáveis
        all_not_verified.append(column.GlobalId)

# Criar um DataFrame para armazenar as dimensões dos pilares
column_data = pd.DataFrame(column_dimensions, columns=[
    "ID do Pilar", "Base (m)", "Altura (m)", "Comprimento (m)"
])

# Criar um DataFrame para os pilares com largura ou altura menor que 19 cm
width_issues_data = pd.DataFrame(all_issues, columns=[
    "ID do Pilar com Largura ou Altura < 19 cm"
])

# Criar um DataFrame para os pilares que não puderam ser verificados
not_verified_data = pd.DataFrame(all_not_verified, columns=[
    "ID do Pilar Não Verificado"
])


"""
Essa parte do código adiciona o comentário de que todos os elementos estão em conformidade
na aba de "elementos não conformes"

"""
# Adicionar mensagem se todos os elementos estão conforme ou não
if not all_issues:
    issues_data = pd.DataFrame([["Todos os elementos estão conforme"]], columns=[
                               "ID do Pilar com Largura ou Altura < 19 cm"])


"""
Essa parte do código adiciona o comentário de que todos os elementos foram verficados
na aba de "elementos não verificados"

"""

# Adicionar mensagem se todos os elementos foram verificados ou não
if not all_not_verified:
    not_verified_data = pd.DataFrame(
        [["Todos os elementos foram verificados"]], columns=["ID do Pilar Não Verificado"])

# Salvar os DataFrames em um arquivo Excel
with pd.ExcelWriter(r"C:/Users/jeffe/OneDrive/Documentos/CEFET/MESTRADO/PYTHON/REVIT/resultado_regra33.xlsx") as writer:
    # Criando a aba das dimensões dos pilares
    column_data.to_excel(writer, sheet_name="Dimensões", index=False)
    # Criando a aba das não conformidades
    width_issues_data.to_excel(
        writer, sheet_name="Elementos em não conformidade", index=False)
    # Criando a aba dos não verificados
    not_verified_data.to_excel(
        writer, sheet_name="Elementos Não Verificados", index=False)

print("\nVerificação concluída e resultados salvos no arquivo Excel.")
