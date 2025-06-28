#REGRA R34
import ifcopenshell
import ifcopenshell.geom
import numpy as np
import pandas as pd

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


# Função para verificar espessura da laje
"""
Se a função encontrar uma inconformidade, ela vai retornar o GlobalID da laje e espessura, além de salvar 
essas inconformidades na variável de registro de todas inconformidades.
Se não encontrar, ela também retorna essa informação.
"""


def verificar_espessura_laje(laje, em_balanco):
    tipo_predefinido = laje.PredefinedType
    espessura = None

    if hasattr(laje, "Representation"):
        for representacao in laje.Representation.Representations:
            print(
                f"Verificando representação: {representacao.RepresentationType}")
            if representacao.RepresentationType == "SweptSolid":
                for item in representacao.Items:
                    if item.is_a("IfcExtrudedAreaSolid"):
                        perfil = item.SweptArea
                        # Profundidade da extrusão (espessura da laje)
                        profundidade = item.Depth
                        print(
                            f"Espessura encontrada (extrusão): {profundidade}")
                        espessura = profundidade

                        # Verificação de espessura com base no tipo de laje
                        if tipo_predefinido == "ROOF" and espessura < 0.07:
                            # Registro de inconformidade para ROOF
                            todas_inconformidades_espessura.append(
                                (laje.GlobalId, espessura))
                            return laje.GlobalId, espessura  # Retorna com erro

                        elif tipo_predefinido == "BASESLAB" and espessura < 0.08:
                            # Registro de inconformidade para BASESLAB
                            todas_inconformidades_espessura.append(
                                (laje.GlobalId, espessura))
                            return laje.GlobalId, espessura  # Retorna com erro

                        elif tipo_predefinido == "FLOOR":
                            if em_balanco and espessura < 0.10:
                                # Registro de inconformidade para FLOOR em balanço
                                todas_inconformidades_espessura.append(
                                    (laje.GlobalId, espessura))
                                return laje.GlobalId, espessura  # Retorna com erro
                            elif not em_balanco and espessura < 0.08:
                                # Registro de inconformidade para FLOOR não em balanço
                                todas_inconformidades_espessura.append(
                                    (laje.GlobalId, espessura))
                                return laje.GlobalId, espessura  # Retorna com erro
                            else:
                                return laje.GlobalId, espessura
    # Se não encontrar, retorna None
    return laje.GlobalId, espessura


# Carregar o arquivo IFC
local_file = r"XXXX"
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
# variável para armazenar as inconformidades
todas_inconformidades_espessura = []
lajes_espessura_ok = []  # Variável agora definida
lajes_verificadas = []  # variável para armazenar as lajes verificadas
lajes_ja_verificadas = set()  # Novo: conjunto para evitar duplicidade

# Inicia o iterador da geometria, para processar e armazenar as lajes em variáveis
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
            em_balanco = num_clashes < quantidade_vertices

            # Verificar a espessura da laje EM BALANÇO
            resultado, espessura = verificar_espessura_laje(laje, em_balanco)
            if espessura is not None:
                if resultado in todas_inconformidades_espessura:
                    todas_inconformidades_espessura.append(
                        (resultado, espessura))
                else:
                    lajes_espessura_ok.append((laje.GlobalId, espessura))

            # Adicionando espessura
            lajes_verificadas.append((laje_id, espessura))
            lajes_ja_verificadas.add(laje_id)  # Marcando como verificada

# Verificar espessuras das lajes que não estão em balanço
"""
A verificação de lajes maciças padrão é mais simples, não é necessário realizar contagem de clashes,
apenas chaamar a função de verificar a espessura das lajes. Se a inconformidade for encontrada, ele da um apend no ID da laje
"""
for laje in lajes_roof + lajes_base + lajes_floor:
    if laje.GlobalId in lajes_ja_verificadas:
        continue  # Pular lajes já verificadas no balanço

    if laje.GlobalId in formas_lajes:
        vertices_superiores = obter_vertices_superiores(
            formas_lajes[laje.GlobalId].geometry.verts)
        if laje.GlobalId in contagem_clashes_laje and contagem_clashes_laje[laje.GlobalId]['clashes'] >= len(vertices_superiores):
            resultado, espessura = verificar_espessura_laje(
                laje, em_balanco=False)
            if espessura is not None:
                if resultado in todas_inconformidades_espessura:
                    todas_inconformidades_espessura.append(
                        (resultado, espessura))
                else:
                    lajes_espessura_ok.append((laje.GlobalId, espessura))

            lajes_verificadas.append((laje.GlobalId, espessura))
            lajes_ja_verificadas.add(laje.GlobalId)

# Exibir resultados
print(f"Total de lajes verificadas: {len(lajes_verificadas)}")
if todas_inconformidades_espessura:
    print("As seguintes lajes não estão de acordo com as regras de espessura:")
    for inconformidade in todas_inconformidades_espessura:
        print(inconformidade)
else:
    print("Todas as lajes estão de acordo com as regras de espessura.")

# Gerar planilha Excel
with pd.ExcelWriter(r"C:/Users/jeffe/OneDrive/Documentos/CEFET/MESTRADO/PYTHON/REVIT/resultado_regra34.xlsx", engine='openpyxl') as writer:
    pd.DataFrame(lajes_verificadas, columns=["Lajes Verificadas", "Espessura"]).to_excel(
        writer, sheet_name="Lajes Verificadas", index=False)
    pd.DataFrame(todas_inconformidades_espessura, columns=["Lajes em Desacordo", "Espessura"]).to_excel(
        writer, sheet_name="Lajes em Desacordo", index=False)
