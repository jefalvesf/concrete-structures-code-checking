#REGRA R48
import ifcopenshell
import ifcopenshell.geom
import pandas as pd

# Funções Auxiliares

"""
Determina a orientação da viga (paralela ao eixo X ou Y) e retorna o XDim correto.
"""


def calcular_xdim(viga_bounds):
    x_length = viga_bounds[1] - viga_bounds[0]
    y_length = viga_bounds[3] - viga_bounds[2]
    z_length = viga_bounds[5] - viga_bounds[4]
    if x_length > y_length:
        return min(y_length, z_length)
    else:
        return min(x_length, z_length)


"""
Essa função é utilizada para associar uma barra a um elemento estrutural.
Em razão da falha dessa associação no esquema IFC. Atualmente, dentro da comunidade, não se conhece 
um software que consiga exportar essa relação. E ainda, não se sabe ao certo, qual relação seria a correta. 
"""


def verificar_limites(ponto, limites):
    return (
        limites[0] <= ponto[0] <= limites[1] and
        limites[2] <= ponto[1] <= limites[3] and
        limites[4] <= ponto[2] <= limites[5]
    )


"""
Essa função recebe os vértices das barras de aço e calcular o centro dela.
"""


def centro_barra(vertices):
    x_coords = [vertices[i] for i in range(0, len(vertices), 3)]
    y_coords = [vertices[i + 1] for i in range(0, len(vertices), 3)]
    z_coords = [vertices[i + 2] for i in range(0, len(vertices), 3)]
    return (
        sum(x_coords) / len(x_coords),
        sum(y_coords) / len(y_coords),
        sum(z_coords) / len(z_coords)
    )


# Leitura do IFC
"""
Função do IfcOpenShell para abrir o arquivo IFC
"""
local_file = r"XXXX"
ifc_file = ifcopenshell.open(local_file)

# Configurações de geometria

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

# Inicialização de listas para armazenar resultados
vigas = []
barras_associadas = []
inconformidades = []
barras_por_viga = {}

# Iteração pelos elementos
"""
Nesta etapa, inicia-se a iteração sobre os elementos
"""
for element in ifc_file.by_type("IfcBeam"):
    shape = ifcopenshell.geom.create_shape(settings, element)
    verts = shape.geometry.verts
    bounds = (
        min(verts[0::3]), max(verts[0::3]),
        min(verts[1::3]), max(verts[1::3]),
        min(verts[2::3]), max(verts[2::3])
    )
    xdim = calcular_xdim(bounds)
    vigas.append({'id': element.GlobalId, 'bounds': bounds, 'xdim': xdim})

for element in ifc_file.by_type("IfcReinforcingBar"):
    if hasattr(element, "ObjectType") and element.ObjectType.upper() == "LIGATURE":
        shape = ifcopenshell.geom.create_shape(settings, element)
        verts = shape.geometry.verts
        bar_center = centro_barra(verts)

        nominal_diameter = None
        for rel in element.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                props = rel.RelatingPropertyDefinition
                if props.is_a("IfcPropertySet") and props.Name == "Pset_ReinforcingBarCommon":
                    for p in props.HasProperties:
                        if p.Name == "NominalDiameter":
                            nominal_diameter = p.NominalValue.wrappedValue / 1000
                            break

        if nominal_diameter is not None:
            for viga in vigas:
                if verificar_limites(bar_center, viga['bounds']):
                    barras_associadas.append(
                        (element.GlobalId, nominal_diameter,
                         viga['id'], viga['xdim'])
                    )
                    break


# Agrupar barras por viga

for barra_id, nominal_diameter, viga_id, xdim in barras_associadas:
    if viga_id not in barras_por_viga:
        barras_por_viga[viga_id] = {'xdim': xdim, 'barras': []}
    barras_por_viga[viga_id]['barras'].append((barra_id, nominal_diameter))



# Verificação da Regra 48 com agrupamento
for viga_id, dados in barras_por_viga.items():
    xdim = dados['xdim']
    for barra_id, nominal_diameter in dados['barras']:
        if xdim is not None:
            if 0.005 <= nominal_diameter < 0.1 * xdim:
                inconformidades.append(
                    [barra_id, nominal_diameter * 1000, viga_id, xdim * 1000, "Regra 48", "OK"]
                )
            else:
                inconformidades.append(
                    [barra_id, nominal_diameter * 1000, viga_id, xdim * 1000, "Regra 48", "NÃO CONFORME"]
                )
        else:
            inconformidades.append(
                [barra_id, nominal_diameter * 1000, viga_id, "-", "Regra 48", "XDim não determinado"]
            )
            
# Filtragem para exportar apenas "NÃO CONFORME"
inconformes_nao_conforme = [
    i for i in inconformidades if i[5] == "NÃO CONFORME"]

# Exportação para Excel (apenas "NÃO CONFORME")

if inconformes_nao_conforme:
    caminho_arquivo = r"C:/Users/jeffe/OneDrive/Documentos/CEFET/MESTRADO/PYTHON/REVIT/resultado_regra48.xlsx"
    colunas = ["ID da Barra", "Diâmetro (mm)", "ID da Viga",
               "XDim da Viga (mm)", "Regra", "Status"]
    df_inconformes_nao_conforme = pd.DataFrame(
        inconformes_nao_conforme, columns=colunas)

    with pd.ExcelWriter(caminho_arquivo, engine='openpyxl') as writer:
        df_inconformes_nao_conforme.to_excel(
            writer, sheet_name="Inconformes", index=False)

    print(f"\n Inconformidades 'NÃO CONFORME' salvas em: {caminho_arquivo}")
else:
    print("\n Todas as barras estão conformes com a Regra 48!")
