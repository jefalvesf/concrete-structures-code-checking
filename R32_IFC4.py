import ifcopenshell
import ifcopenshell.geom
import numpy as np

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

    # Largura (menor dimensão no plano XY)
    largura = min(dim_x, dim_y)

    # Altura (variação no eixo Z)
    altura = dim_z

    return comprimento, largura, altura


"""
Função do IfcOpenShell para abrir o arquivo IFC
"""

local_file = r"C:/Users/jeffe/Downloads/RELATIONSHIP_RVT25.ifc"
ifc_file = ifcopenshell.open(local_file)

# Configurações de geometria
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

# Inicializar variáveis para armazenar dados resultados
beams = ifc_file.by_type("IfcBeam")
beam_dimensions = []
all_width_issues = []
all_not_verified = []

"""
Nesta etapa-se inicia-se o processamento da geometria.
"""
# Iterar pelas vigas no modelo
for beam in beams:
    try:
        # Criar a geometria da viga
        shape = ifcopenshell.geom.create_shape(settings, beam)
        verts = shape.geometry.verts

        # Calcular dimensões da viga
        comprimento, largura, altura = calcular_dimensoes(verts)

        # Verificação da largura
        if largura < 0.12:  # Se a largura for menor que 12 cm
            all_width_issues.append(beam.GlobalId)

        # Armazenar o ID e as dimensões da viga
        beam_dimensions.append((beam.GlobalId, comprimento, largura, altura))

    except Exception as e:
        # Caso ocorra algum erro, adicionar à lista de não verificáveis
        all_not_verified.append(beam.GlobalId)

# Imprimir as dimensões verificadas
print("Dimensões de todas as vigas verificadas:")
print("ID da Viga        | Comprimento (m) | Largura (m) | Altura (m)")
print("-" * 50)
for beam_id, comprimento, largura, altura in beam_dimensions:
    print(f"{beam_id} | {comprimento:.2f} | {largura:.2f} | {altura:.2f}")

# Imprimir as vigas com largura menor que 12 cm
if all_width_issues:
    print("\nAs seguintes vigas têm largura menor que 12 cm:")
    for issue in all_width_issues:
        print(issue)
else:
    print("\nTodas as vigas estão dentro do padrão de largura mínima.")

# Imprimir as vigas que não puderam ser verificadas
if all_not_verified:
    print("\nAs seguintes vigas não puderam ser verificadas:")
    for unverified in all_not_verified:
        print(unverified)

print("\nVerificação concluída.")
