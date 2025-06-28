import ifcopenshell
import ifcopenshell.geom
import multiprocessing

# Abre o arquivo IFC
local_file = r"C:/Users/jeffe/Downloads/RELATIONSHIP_RVT25.ifc"
ifc_file = ifcopenshell.open(local_file)

# Configurações da geometria
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)  # Usa coordenadas globais

# Inicializa o iterador de geometria
iterator = ifcopenshell.geom.iterator(
    settings, ifc_file, multiprocessing.cpu_count())


# Dicionários para armazenar informações de vigas e barras
vigas = []  # List of dicts with 'id', 'bounds', 'xdim'
# List to store tuples (barra_id, nominal_diameter, viga_id, xdim)
barras_associadas = []

# Função para obter o XDim de uma viga via seu tipo


def get_xdim_from_beam(element, ifc_file):
    xdim = None
    if hasattr(element, "IsTypedBy"):
        for rel in element.IsTypedBy:
            if rel.is_a("IfcRelDefinesByType"):
                beam_type = rel.RelatingType
                if hasattr(beam_type, "Representation"):
                    for representation in beam_type.Representation.Representations:
                        if representation.RepresentationType == "MappedRepresentation":
                            for item in representation.Items:
                                if item.is_a("IfcMappedItem") and hasattr(item, "MappingSource"):
                                    mapped_rep = item.MappingSource.MappedRepresentation
                                    for mapped_item in mapped_rep.Items:
                                        if mapped_item.is_a("IfcExtrudedAreaSolid"):
                                            profile = mapped_item.SweptArea
                                            if profile.is_a("IfcRectangleProfileDef"):
                                                return profile.XDim
                        elif representation.RepresentationType == "SweptSolid":
                            for item in representation.Items:
                                if item.is_a("IfcExtrudedAreaSolid"):
                                    profile = item.SweptArea
                                    if profile.is_a("IfcRectangleProfileDef"):
                                        return profile.XDim
    return xdim

# Função para determinar o XDim com base na orientação da viga


def calculate_xdim_from_bounds(viga_bounds):
    """
    Determina a orientação da viga (paralela ao eixo X ou Y) e retorna o XDim correto.
    """
    x_length = viga_bounds[1] - viga_bounds[0]  # Comprimento no eixo X
    y_length = viga_bounds[3] - viga_bounds[2]  # Comprimento no eixo Y
    z_length = viga_bounds[5] - viga_bounds[4]  # Altura no eixo Z

    if x_length > y_length:  # Viga paralela ao eixo X
        # XDim será a menor dimensão perpendicular ao eixo X
        xdim = min(y_length, z_length)
    else:  # Viga paralela ao eixo Y
        # XDim será a menor dimensão perpendicular ao eixo Y
        xdim = min(x_length, z_length)

    return xdim


# Processa os elementos geométricos
if iterator.initialize():
    while True:
        shape = iterator.get()
        element = ifc_file.by_id(shape.id)
        element_type = element.is_a()

        # Processa vigas (IfcBeam)
        if element_type == "IfcBeam":
            verts = shape.geometry.verts
            viga_bounds = (
                min(verts[0::3]), max(verts[0::3]),
                min(verts[1::3]), max(verts[1::3]),
                min(verts[2::3]), max(verts[2::3])
            )
            xdim = get_xdim_from_beam(element, ifc_file)
            if xdim is None:
                xdim = calculate_xdim_from_bounds(viga_bounds)
            vigas.append(
                {'id': element.GlobalId, 'bounds': viga_bounds, 'xdim': xdim})

        # Processa barras de reforço (IfcReinforcingBar)
        elif element_type == "IfcReinforcingBar":
            if hasattr(element, "ObjectType") and element.ObjectType == "LIGATURE":
                nominal_diameter = None
                for pset in element.IsDefinedBy:
                    if pset.is_a("IfcRelDefinesByProperties"):
                        properties = pset.RelatingPropertyDefinition
                        if properties.is_a("IfcPropertySet") and properties.Name == "Pset_ReinforcingBarCommon":
                            for prop in properties.HasProperties:
                                if prop.Name == "NominalDiameter":
                                    # Converte o diâmetro de milímetros para metros
                                    nominal_diameter = prop.NominalValue.wrappedValue / 1000
                                    break

                if nominal_diameter is not None:
                    verts = shape.geometry.verts
                    bar_center = (
                        sum(verts[0::3]) / len(verts[0::3]),
                        sum(verts[1::3]) / len(verts[1::3]),
                        sum(verts[2::3]) / len(verts[2::3])
                    )

                    for viga in vigas:
                        viga_bounds = viga['bounds']
                        if (
                            viga_bounds[0] <= bar_center[0] <= viga_bounds[1] and
                            viga_bounds[2] <= bar_center[1] <= viga_bounds[3] and
                            viga_bounds[4] <= bar_center[2] <= viga_bounds[5]
                        ):
                            barras_associadas.append(
                                (element.GlobalId, nominal_diameter,
                                 viga['id'], viga['xdim'])
                            )
                            break

        if not iterator.next():
            break

# Verificação da Regra 48
print("\nVerificação da Regra 48:")
for barra_id, nominal_diameter, viga_id, xdim in barras_associadas:
    if xdim is not None:
        if nominal_diameter >= 0.005 and nominal_diameter < 0.1 * xdim:
            print(f"Barra {barra_id} na viga {
                  viga_id}: Tudo OK com a regra 48.")
        else:
            print(f"Barra {barra_id} na viga {
                  viga_id}: Não está OK com a regra 48.")
    else:
        print(f"Barra {barra_id} na viga {
              viga_id}: Não foi possível determinar o XDim da viga.")
