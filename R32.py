#REGRA R32
import ifcopenshell
import ifcopenshell.geom
import numpy as np
import pandas as pd

# Função para calcular as dimensões com base nos vértices


def calcular_dimensoes(verts):
    """
    Calcula comprimento, largura e altura da viga, assumindo as seguintes premissas:
    Comprimento é a maior projeção no plano XY.
    Largura é a menor projeção no plano XY.
    Altura é a variação no eixo Z.
    """
    vertices = np.array(verts).reshape(-1, 3)

    # Dimensões no espaço
    dim_x = vertices[:, 0].max() - vertices[:, 0].min()  # Variação em X
    dim_y = vertices[:, 1].max() - vertices[:, 1].min()  # Variação em Y
    dim_z = vertices[:, 2].max() - vertices[:, 2].min()  # Variação em Z

    # Comprimento (maior dimensão no plano XY)
    comprimento = max(dim_x, dim_y)

    # Largura  (menor dimensão no plano XY)
    largura = min(dim_x, dim_y)

    # Altura (variação no eixo Z)
    altura = dim_z

    return comprimento, largura, altura


"""
Função do IfcOpenShell para abrir o arquivo IFC
"""
local_file = r"XXXX"
ifc_file = ifcopenshell.open(local_file)

# Configurações de geometria
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

# Inicializar variáveis para armazenar dados resultados
beams = ifc_file.by_type("IfcBeam")
beam_dimensions = []
all_width_issues = []  # Vigas com largura menor que 12 cm
all_not_verified = []  # Vigas que não puderam ser verificadas


# Iterar pelas vigas no modelo
for beam in beams:
    try:
        # Criar a geometria da viga
        """
        Nesta etapa inicia-se o processamento da geometria.
        """
        shape = ifcopenshell.geom.create_shape(settings, beam)
        verts = shape.geometry.verts

        # Calcular dimensões da viga
        """
        Nesta etapa, passas-se os vértices e chama-se a função para calcular dimensões
        """
        comprimento, largura, altura = calcular_dimensoes(verts)

        # Verificação da largura
        """
        Etapa para verificar a largura mínima conforme requisito normativo da norma brasileira NBR 6118
        """
        if largura < 0.12:  # Se a largura for menor que 12 cm
            all_width_issues.append(beam.GlobalId)

        # Armazenar o ID e as dimensões da viga
        beam_dimensions.append((beam.GlobalId, comprimento, largura, altura))

    except Exception as e:
        # Caso ocorra algum erro, adicionar à lista de não verificáveis
        all_not_verified.append(beam.GlobalId)

# Criar um DataFrame para armazenar as dimensões das vigas
beam_data = pd.DataFrame(beam_dimensions, columns=[
                         "ID da Viga", "Comprimento (m)", "Largura (m)", "Altura (m)"])

# Criar um DataFrame para as vigas com largura menor que 12 cm
width_issues_data = pd.DataFrame(all_width_issues, columns=[
                                 "ID da Viga com Largura Menor que 12 cm"])

# Criar um DataFrame para as vigas que não puderam ser verificadas
not_verified_data = pd.DataFrame(all_not_verified, columns=[
                                 "ID da Viga Não Verificada"])

"""
Essa parte do código adiciona o comentário de que todos os elementos estão em conformidade
na aba de "elementos não conformes"

"""
# Adicionar mensagem se todos os elementos estão conforme ou não
if not all_width_issues:
    width_issues_data = pd.DataFrame([["Todos os elementos estão conforme"]], columns=[
                                     "ID da Viga com Largura Menor que 12 cm"])

"""
Essa parte do código adiciona o comentário de que todos os elementos foram verficados
na aba de "elementos não verificados"

"""


# Adicionar mensagem se todos os elementos foram verificados ou não
if not all_not_verified:
    not_verified_data = pd.DataFrame(
        [["Todos os elementos foram verificados"]], columns=["ID da Viga Não Verificada"])

# Salvar os DataFrames em um arquivo Excel
with pd.ExcelWriter(r"C:/Users/jeffe/OneDrive/Documentos/CEFET/MESTRADO/PYTHON/REVIT/resultado_regra32.xlsx") as writer:
    beam_data.to_excel(writer, sheet_name="Dimensões",
                       index=False)  # Criando a aba das dimensões da viga
    width_issues_data.to_excel(
        # Criando a aba das não conformidades
        writer, sheet_name="Largura < 12 cm", index=False)
    not_verified_data.to_excel(
        # Criando a aba do que não foi verificado
        writer, sheet_name="Não Verificadas", index=False)

print("\nVerificação concluída e resultados salvos no arquivo Excel.")
