import ifcopenshell
import ifcopenshell.geom
import numpy as np

# Carregar o arquivo IFC
local_file = r"C:/Users/jeffe/Downloads/RELATIONSHIP_RVT25.ifc"
ifc_file = ifcopenshell.open(local_file)

# Configurações de geometria
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

# Função para calcular as dimensões com base nos vértices


def calculate_dimensions_from_vertices(verts):
    """
    Calcula comprimento, largura e altura da geometria, assumindo:
    - Comprimento: maior projeção no plano XY.
    - Largura: menor projeção no plano XY.
    - Altura: variação no eixo Z.
    """
    vertices = np.array(verts).reshape(-1, 3)

    # Dimensões no espaço
    dim_x = abs(vertices[:, 0].max() - vertices[:, 0].min())  # Variação em X
    dim_y = abs(vertices[:, 1].max() - vertices[:, 1].min())  # Variação em Y
    dim_z = abs(vertices[:, 2].max() - vertices[:, 2].min())  # Variação em Z

    # Comprimento (maior dimensão no plano XY)
    length = max(dim_x, dim_y)

    # Largura (menor dimensão no plano XY)
    width = min(dim_x, dim_y)

    # Altura (variação no eixo Z)
    height = dim_z

    return length, width, height, dim_x, dim_y


# Inicializar variáveis para armazenar resultados
columns = ifc_file.by_type("IfcColumn")
column_dimensions = []
all_not_verified = []
rule_51_issues = []

# Iterar pelos pilares no modelo
for column in columns:
    try:
        # Criar a geometria do pilar
        shape = ifcopenshell.geom.create_shape(settings, column)
        verts = shape.geometry.verts

        # Calcular dimensões do pilar
        length, width, height, dim_x, dim_y = calculate_dimensions_from_vertices(
            verts)

        # Verificação da regra 51: maior dimensão (X ou Y) não pode ser maior que 5x a menor
        max_dim = max(dim_x, dim_y)
        min_dim = min(dim_x, dim_y)

        if max_dim > 5 * min_dim:
            rule_51_issues.append(column.GlobalId)

        # Armazenar o ID e as dimensões do pilar
        column_dimensions.append(
            (column.GlobalId, dim_x, dim_y, height, max_dim, min_dim))

    except Exception as e:
        # Caso ocorra algum erro, adicionar à lista de não verificáveis
        all_not_verified.append(column.GlobalId)

# Imprimir as dimensões verificadas
print("Dimensões de todos os pilares verificadas:")
print("ID do Pilar        | Largura (X) (m) | Comprimento (Y) (m) | Altura (Z) (m) | Maior Dimensão (X,Y) (m) | Menor Dimensão (X,Y) (m)")
print("-" * 100)
for column_id, dim_x, dim_y, height, max_dim, min_dim in column_dimensions:
    print(f"{column_id} | {dim_x:.2f} | {dim_y:.2f} | {
          height:.2f} | {max_dim:.2f} | {min_dim:.2f}")

# Imprimir os pilares que não atendem à regra 51
if rule_51_issues:
    print("\nOs seguintes pilares não atendem à Regra 51 (Maior dimensão X ou Y > 5x Menor dimensão X ou Y):")
    for issue in rule_51_issues:
        print(issue)
else:
    print("\nTodos os pilares estão dentro do padrão da Regra 51.")

# Imprimir os pilares que não puderam ser verificados
if all_not_verified:
    print("\nOs seguintes pilares não puderam ser verificados:")
    for unverified in all_not_verified:
        print(unverified)

print("\nVerificação concluída.")
