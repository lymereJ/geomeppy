"""Tool for visualising geometry."""
from typing import Optional  # noqa

from eppy.function_helpers import getcoords
from eppy.iddcurrent import iddcurrent
from eppy.modeleditor import IDF
from six import StringIO
from six.moves.tkinter import TclError

try:
    from mpl_toolkits.mplot3d import Axes3D  # noqa
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import matplotlib.pyplot as plt
except (ImportError, RuntimeError):
    # this isn't always needed so we can ignore if it's not present
    pass


def view_idf(fname=None, idf_txt=None, test=False):
    # type: (Optional[str], Optional[str], Optional[bool]) -> None
    """Display an IDF for inspection.

    :param fname: Path to the IDF.
    :param idf_txt: The string representation of an IDF.
    """
    try:
        plt.figure()
    except TclError:
        # this is as expected on the test server
        return
    if fname and idf_txt:
        raise ValueError("Pass either fname or idf_txt, not both.")
    # set the IDD for the version of EnergyPlus
    iddfhandle = StringIO(iddcurrent.iddtxt)
    if IDF.getiddname() is None:
        IDF.setiddname(iddfhandle)

    if fname:
        # import the IDF
        idf = IDF(fname)
    elif idf_txt:
        idf = IDF()
        idf.initreadtxt(idf_txt)
    # create the figure and add the surfaces
    ax = plt.axes(projection="3d")
    collections = _get_collections(idf, opacity=0.5)
    for c in collections:
        ax.add_collection3d(c)

    # calculate and set the axis limits
    limits = _get_limits(collections=collections)
    ax.set_xlim(limits["x"])
    ax.set_ylim(limits["y"])
    ax.set_zlim(limits["z"])

    if not test:
        plt.show()


def view_polygons(polygons):
    """Display a collection of polygons for inspection.

    :param polygons: A dict keyed by colour, containing Polygon3D objects to show in that colour.
    """
    # create the figure and add the surfaces
    plt.figure()
    ax = plt.axes(projection="3d")

    collections = _make_collections(polygons, opacity=0.5)

    for c in collections:
        ax.add_collection3d(c)

    # calculate and set the axis limits
    limits = _get_limits(polygons=polygons)
    ax.set_xlim(limits["x"])
    ax.set_ylim(limits["y"])
    ax.set_zlim(limits["z"])

    plt.show()


def _get_geometry_rules(idf):
    """Get the geometry rules from the IDF
    """
    rule_types = ["GLOBALGEOMETRYRULES"]
    rule = [idf.idfobjects[rule_type] for rule_type in rule_types]

    return rule


def _get_zones(idf):
    """Get the zones from the IDF
    """
    zone_types = ["ZONE"]
    zones = [idf.idfobjects[zone_type] for zone_type in zone_types]

    return zones


def _get_surfaces(idf):
    """Get the surfaces from the IDF.
    """
    surface_types = ["BUILDINGSURFACE:DETAILED", "FENESTRATIONSURFACE:DETAILED"]
    surfaces = []
    for surface_type in surface_types:
        surfaces.extend(idf.idfobjects[surface_type])

    return surfaces


def _get_shading(idf):
    """Get the shading surfaces from the IDF."""
    shading_types = ["SHADING:ZONE:DETAILED"]
    shading = []
    for shading_type in shading_types:
        shading.extend(idf.idfobjects[shading_type])

    return shading


def _get_collections(idf, opacity=1):
    """Set up 3D collections for each surface type."""
    surfaces = _get_surfaces(idf)
    if _get_geometry_rules(idf)[0].Coordinate_System.lower() == "relative":
        zones = _get_zones(idf)
    else:
        zones = []

    # set up the collections
    walls = _get_collection("wall", surfaces, opacity, zones, facecolor="lightyellow")
    floors = _get_collection("floor", surfaces, opacity, zones, facecolor="dimgray")
    roofs = _get_collection("roof", surfaces, opacity, zones, facecolor="firebrick")
    windows = _get_collection(
        "window", surfaces, opacity, zones, facecolor="cornflowerblue"
    )

    shading_surfaces = _get_shading(idf)
    shading = Poly3DCollection(
        [getcoords(s) for s in shading_surfaces],
        alpha=opacity,
        facecolor="darkolivegreen",
        edgecolors="black",
    )

    return walls, roofs, floors, windows, shading


def _get_collection(
    surface_type, surfaces, opacity, zones, facecolor, edgecolors="black"
):
    """Make collections from a list of EnergyPlus surfaces."""
    origin = {}

    # if coordinate system is relative,
    # get the zone origin coordinates for each surface
    if zones:
        coords = []
        for surface in surfaces:
            if surface.Surface_Type.lower() != "window":
                zname = surface.Zone_Name
                for zone in zones:
                    if zone.Name == zname:
                        origin[surface.Name] = (
                            zone.X_Origin,
                            zone.Y_Origin,
                            zone.Z_Origin,
                        )
        for surface in surfaces:
            if surface.Surface_Type.lower() == "window":
                origin[surface.Name] = origin[surface.Building_Surface_Name]
            if surface.Surface_Type.lower() == surface_type.lower():
                adj_coords = []
                if surface.Surface_Type.lower() == "window":
                    origin[surface.Name]
                for crd_set in getcoords(surface):
                    adj_coords.append(
                        tuple(
                            [
                                crd + org
                                for crd, org in zip(crd_set, origin[surface.Name])
                            ]
                        )
                    )
                coords.append(adj_coords)
    else:
        coords = [
            getcoords(surface)
            for surface in surfaces
            if surface.Surface_Type.lower() == surface_type.lower()
        ]
    trimmed_coords = [c for c in coords if c]  # dump any empty surfaces
    collection = Poly3DCollection(
        trimmed_coords, alpha=opacity, facecolor=facecolor, edgecolors=edgecolors
    )
    return collection


def _make_collections(polygons, opacity=1):
    """Make collections from a dict of polygons."""
    collection = []
    for color in polygons:
        collection.append(
            Poly3DCollection(
                [p.points_matrix for p in polygons[color]],
                alpha=opacity,
                facecolor=color,
                edgecolors="black",
            )
        )
    return collection


def _get_limits(idf=None, polygons=None, collections=None):
    """Get limits for the x, y and z axes so the plot is fitted to the axes."""
    if polygons:
        x = [pt[0] for color in polygons for p in polygons[color] for pt in p]
        y = [pt[1] for color in polygons for p in polygons[color] for pt in p]
        z = [pt[2] for color in polygons for p in polygons[color] for pt in p]

    elif idf:
        surfaces = _get_surfaces(idf)

        x = [pt[0] for s in surfaces for pt in getcoords(s)]
        y = [pt[1] for s in surfaces for pt in getcoords(s)]
        z = [pt[2] for s in surfaces for pt in getcoords(s)]

    elif collections:

        x = []
        y = []
        z = []

        for c in collections:
            xdata, ydata, zdata, _ = c._vec
            for x_i, y_i, z_i in zip(xdata, ydata, zdata):
                x.append(x_i)
                y.append(y_i)
                z.append(z_i)

    max_delta = max((max(x) - min(x)), (max(y) - min(y)), (max(z) - min(z)))

    return {
        "x": (min(x), min(x) + max_delta),
        "y": (min(y), min(y) + max_delta),
        "z": (min(z), min(y) + max_delta),
    }


def main(fname=None, polygons=None):
    if fname:
        view_idf(fname)
    elif polygons:
        view_polygons(polygons)


if __name__ == "__main__":
    main()
