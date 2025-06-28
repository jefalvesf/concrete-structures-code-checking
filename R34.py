import ifcopenshell
import ifcopenshell.geom
import numpy as np

# Função para filtrar vértices do plano superior da laje


def obter_vertices_superiores(verts):
    vertices = np.array(verts).reshape(-1, 3)
    max_z = np.max(vertices[:, 2])  # Pega o maior valor de Z
    vertices_superiores = vertices[vertices[:, 2] == max_z]
    return vertices_superiores

# Função para verificar clashes


def verificar_clashes_laje(clash):
    element1 = clash.a
    element2 = clash.b
    a_global_id = element1.get_argument(0)
    b_global_id = element2.get_argument(0)
    a_ifc_class = element1.is_a()
    b_ifc_class = element2.is_a()

    if a_ifc_class == "IfcSlab":
        if a_global_id not in contagem_clashes_laje:
            contagem_clashes_laje[a_global_id] = {'clashes': 0, 'vertices': 0}
        contagem_clashes_laje[a_global_id]['clashes'] += 1
    elif b_ifc_class == "IfcSlab":
        if b_global_id not in contagem_clashes_laje:
            contagem_clashes_laje[b_global_id] = {'clashes': 0, 'vertices': 0}
        contagem_clashes_laje[b_global_id]['clashes'] += 1


# Função para verificar a espessura da laje
"""
Se a função encontrar uma inconformidade, ela vai retornar o GlobalID da laje e espessura, se não, ela não retorna nada.
"""


def verificar_espessura_laje(laje, em_balanco):
    tipo_predefinido = laje.PredefinedType
    if hasattr(laje, "Representation"):
        for representacao in laje.Representation.Representations:
            if representacao.RepresentationType == "SweptSolid":
                for item in representacao.Items:
                    if item.is_a("IfcExtrudedAreaSolid"):
                        perfil = item.SweptArea
                        if perfil.is_a("IfcRectangleProfileDef"):
                            espessura = item.Depth
                            # Verificação de espessura com base no tipo de laje
                            if tipo_predefinido == "ROOF" and espessura < 0.07:
                                return laje.GlobalId
                            elif tipo_predefinido == "BASESLAB" and espessura < 0.08:
                                return laje.GlobalId
                            elif tipo_predefinido == "FLOOR":
                                if em_balanco and espessura < 0.10:
                                    return laje.GlobalId
                                elif not em_balanco and espessura < 0.08:
                                    return laje.GlobalId
    return None


# Carregar o arquivo IFC
local_file = r"C:/Users/jeffe/Downloads/RELATIONSHIP_RVT25.ifc"
ifc_file = ifcopenshell.open(local_file)

# Inicializar o tree usando triangulação
"""
tree é um recurso do Ifcopenshell para verificar proximidade entre elementos determinados
segundo uma folga pré-definida de distância entre eles.
"""
tree = ifcopenshell.geom.tree()
settings = ifcopenshell.geom.settings()
iterator = ifcopenshell.geom.iterator(settings, ifc_file)

# Inicializar variáveis para armazenar dados e resultados
lajes = ifc_file.by_type('IfcSlab')
pilares = ifc_file.by_type('IfcColumn')
lajes_floor = []
lajes_base = []
lajes_roof = []
contagem_clashes_laje = {}  # Dicionário para contar clashes por laje
formas_lajes = {}  # Dicionário para armazenar as formas geométricas das lajes
todas_inconformidades_espessura = []  # variável para armazenar as informodiades
lajes_verificadas = []  # variável para armazenar as lajes verificadas

"""
Nesta etapa, inicia-se o iterador da geometrica, para processar e armazenar as lajes em variáveis.
"""
if iterator.initialize():
    while True:
        shape = iterator.get()
        element = ifc_file.by_id(shape.id)

        if element.is_a("IfcSlab"):
            formas_lajes[element.GlobalId] = shape

        tree.add_element(shape)

        if not iterator.next():
            break

# Associação das variáveis para cada tipo de laje
"""
Nesta etapa, cada tipo de laje é associada a uma variável diferente,
haja vista que os critérios variam em função das diferentes funções das lajes. 
"""
for laje in lajes:
    if laje.PredefinedType == "FLOOR":
        lajes_floor.append(laje)
    elif laje.PredefinedType == "BASESLAB":
        lajes_base.append(laje)
    elif laje.PredefinedType == "ROOF":
        lajes_roof.append(laje)

# Verificar clashes entre lajes e pilares
"""
Essa verificação é necessária para saber quais lajes estão ou não em balanço. Ou seja,
lajes que não possuem apoio nas suas estremidades.  Então essa parte do código cria a variável clashe
que usa o tree do ifcopenhsell, e depois faz um loop para verificar todos os clashes de modo a contabilizar,
chamando a função verficiar_clashes_laje. 
"""
clashes = tree.clash_clearance_many(
    lajes_floor, pilares, clearance=1, check_all=False)

for clash in clashes:
    verificar_clashes_laje(clash)


# Verificar lajes em balanço e espessuras
"""
A verificação da laje em balanço necessida de uma lógica maior, pois não é explicito a informação 
de que a laje está em balanço. 
"""

for laje in lajes_floor:
    laje_id = laje.GlobalId
    if laje_id in formas_lajes:
        forma_laje = formas_lajes[laje_id]
        vertices_superiores = obter_vertices_superiores(
            forma_laje.geometry.verts)
        quantidade_vertices = len(vertices_superiores)

        if laje_id in contagem_clashes_laje:
            num_clashes = contagem_clashes_laje[laje_id]['clashes']
            contagem_clashes_laje[laje_id]['vertices'] = quantidade_vertices
            # Aqui de fato entra a lógica se está em balanço ou não, se tem apoio em todos os vértices ou não
            em_balanco = num_clashes < quantidade_vertices

            # Verificar a espessura da laje EM BALANÇO
            inconformidade = verificar_espessura_laje(laje, em_balanco)
            if inconformidade:
                todas_inconformidades_espessura.append(inconformidade)

            # Imprimir a verificação de balanço e espessura
            print(
                f"Laje {laje_id}: {quantidade_vertices} vértices (superior), {num_clashes} clashes")
            if em_balanco:
                print(f"Laje {laje_id} está em balanço")
            else:
                print(f"Laje {laje_id} não está em balanço")
        lajes_verificadas.append(laje_id)


# Verificar espessuras das lajes de ROOF e BASESLAB

"""
A verificação de lajes maciças padrão é mais simples, não é necessário realizar contagem de clashes,
apenas chaamar a função de verificar a espessura das lajes. Se a inconformidade for encontrada, ele da um apend no ID da laje
"""
for laje in lajes_roof + lajes_base:
    inconformidade = verificar_espessura_laje(laje, em_balanco=False)
    if inconformidade:
        todas_inconformidades_espessura.append(inconformidade)
    lajes_verificadas.append(laje.GlobalId)

# Exibir resultados
print(f"Total de lajes verificadas: {len(lajes_verificadas)}")
if todas_inconformidades_espessura:
    print("As seguintes lajes não estão de acordo com as regras de espessura:")
    for inconformidade in todas_inconformidades_espessura:
        print(inconformidade)
else:
    print("Todas as lajes estão de acordo com as regras de espessura.")
