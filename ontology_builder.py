"""
Build and serialise the London Underground ontology graph.

This module uses rdflib to declare ontology classes, object properties, datatype
properties, and serialisation to Turtle.
"""

# pylint: disable=invalid-name,line-too-long

from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD


def add_class(graph: Graph, class_iri, label: str, comment: str):
    """Add an OWL class with English label and comment to the graph."""
    graph.add((class_iri, RDF.type, OWL.Class))
    graph.add((class_iri, RDFS.label, Literal(label, lang="en")))
    graph.add((class_iri, RDFS.comment, Literal(comment, lang="en")))


def add_object_property(graph: Graph, prop_iri, label: str, comment: str, domain=None, range_=None):
    """Add an OWL object property with optional domain and range."""
    graph.add((prop_iri, RDF.type, OWL.ObjectProperty))
    graph.add((prop_iri, RDFS.label, Literal(label, lang="en")))
    graph.add((prop_iri, RDFS.comment, Literal(comment, lang="en")))
    if domain is not None:
        graph.add((prop_iri, RDFS.domain, domain))
    if range_ is not None:
        graph.add((prop_iri, RDFS.range, range_))


def add_datatype_property(graph: Graph, prop_iri, label: str, comment: str, domain=None, range_=None):
    """Add an OWL datatype property with optional domain and range."""
    graph.add((prop_iri, RDF.type, OWL.DatatypeProperty))
    graph.add((prop_iri, RDFS.label, Literal(label, lang="en")))
    graph.add((prop_iri, RDFS.comment, Literal(comment, lang="en")))
    if domain is not None:
        graph.add((prop_iri, RDFS.domain, domain))
    if range_ is not None:
        graph.add((prop_iri, RDFS.range, range_))


def main():
    """Construct the ontology graph and serialise it to Turtle."""
    graph = Graph()

    # ------------------------------------------------------------------
    # Namespaces
    # ------------------------------------------------------------------
    EX = Namespace("http://example.org/ontology-express#")
    TMFAC = Namespace("https://w3id.org/transmodel/facilities#")
    TMJ = Namespace("https://w3id.org/transmodel/journeys#")
    TIME = Namespace("http://www.w3.org/2006/time#")

    graph.bind("ex", EX)
    graph.bind("tmfac", TMFAC)
    graph.bind("tmj", TMJ)
    graph.bind("time", TIME)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    graph.bind("owl", OWL)
    graph.bind("xsd", XSD)

    # ------------------------------------------------------------------
    # Ontology declaration
    # ------------------------------------------------------------------
    ontology_iri = URIRef("http://example.org/ontology-express")
    graph.add((ontology_iri, RDF.type, OWL.Ontology))
    graph.add((ontology_iri, RDFS.label, Literal("London Underground Ontology Foundation", lang="en")))
    graph.add((
        ontology_iri,
        RDFS.comment,
        Literal(
            "A TBox ontology for modelling London Underground stations, lines, routes, incidents, accessibility, maintenance, and rolling stock in line with the defined competency questions.",
            lang="en",
        ),
    ))

    # Import only reused external ontologies
    graph.add((ontology_iri, OWL.imports, URIRef("https://w3id.org/transmodel/facilities#")))
    graph.add((ontology_iri, OWL.imports, URIRef("https://w3id.org/transmodel/journeys#")))
    graph.add((ontology_iri, OWL.imports, URIRef("http://www.w3.org/2006/time")))

    # ------------------------------------------------------------------
    # Classes
    # ------------------------------------------------------------------
    classes = {
        EX.UndergroundStation: (
            "Underground Station",
            "A London Underground station represented as a stop place where passengers can access rail services."
        ),
        EX.InterchangeStation: (
            "Interchange Station",
            "A London Underground station that provides interchange between two or more Underground lines."
        ),
        EX.UndergroundLine: (
            "Underground Line",
            "A named London Underground line such as the Victoria Line or Circle Line."
        ),
        EX.UndergroundRoute: (
            "Underground Route",
            "A route associated with operation of a London Underground line such as West Ruislip to Epping."
        ),
        EX.Incident: (
            "Incident",
            "An operational incident reported within the London Underground network."
        ),
        EX.DisruptionEvent: (
            "Disruption Event",
            "An incident that disrupts normal operation of one or more London Underground lines."
        ),
        EX.DelayEvent: (
            "Delay Event",
            "A disruption event that causes a measurable service delay on the London Underground."
        ),
        EX.ClosureEvent: (
            "Closure Event",
            "A disruption event in which a station or service is closed temporarily."
        ),
        EX.MaintenanceEvent: (
            "Maintenance Event",
            "A planned engineering or maintenance activity affecting the London Underground network."
        ),
        EX.BusReplacementService: (
            "Bus Replacement Service",
            "An alternative bus service provided when a London Underground station or service is unavailable."
        ),
        EX.RollingStockType: (
            "Rolling Stock Type",
            "A type of train stock used on a London Underground line."
        ),
        EX.WheelchairAccessibilityAssessment: (
            "Wheelchair Accessibility Assessment",
            "An accessibility assessment describing wheelchair access at a London Underground station."
        ),
    }

    for iri, (label, comment) in classes.items():
        add_class(graph, iri, label, comment)

    # ------------------------------------------------------------------
    # Local subclass hierarchy
    # ------------------------------------------------------------------
    graph.add((EX.InterchangeStation, RDFS.subClassOf, EX.UndergroundStation))
    graph.add((EX.DisruptionEvent, RDFS.subClassOf, EX.Incident))
    graph.add((EX.DelayEvent, RDFS.subClassOf, EX.DisruptionEvent))
    graph.add((EX.ClosureEvent, RDFS.subClassOf, EX.DisruptionEvent))
    graph.add((EX.MaintenanceEvent, RDFS.subClassOf, EX.DisruptionEvent))

    # ------------------------------------------------------------------
    # External subclass mappings
    # ------------------------------------------------------------------
    graph.add((EX.UndergroundStation, RDFS.subClassOf, TMFAC.StopPlace))
    graph.add((EX.UndergroundLine, RDFS.subClassOf, TMJ.Line))
    graph.add((EX.UndergroundRoute, RDFS.subClassOf, TMJ.Route))
    graph.add((EX.RollingStockType, RDFS.subClassOf, TMFAC.VehicleType))
    graph.add((EX.WheelchairAccessibilityAssessment, RDFS.subClassOf, TMFAC.AccessibilityAssessment))

    # ------------------------------------------------------------------
    # Object properties
    # ------------------------------------------------------------------
    add_object_property(
        graph,
        EX.servedByLine,
        "served by line",
        "Relates a London Underground station to a line that serves it.",
        EX.UndergroundStation,
        EX.UndergroundLine,
    )
    add_object_property(
        graph,
        EX.interchangesWithLine,
        "interchanges with line",
        "Relates an interchange station to a line available for interchange at that station.",
        EX.InterchangeStation,
        EX.UndergroundLine,
    )
    add_object_property(
        graph,
        EX.lineHasRoute,
        "line has route",
        "Relates a London Underground line to one of its associated routes.",
        EX.UndergroundLine,
        EX.UndergroundRoute,
    )
    add_object_property(
        graph,
        EX.routeServesStop,
        "route serves stop",
        "Relates a London Underground route to a station served by that route.",
        EX.UndergroundRoute,
        EX.UndergroundStation,
    )
    add_object_property(
        graph,
        EX.affectsLine,
        "affects line",
        "Relates a disruption event to a London Underground line affected by the disruption.",
        EX.DisruptionEvent,
        EX.UndergroundLine,
    )
    add_object_property(
        graph,
        EX.occursAtStation,
        "occurs at station",
        "Relates an incident to the London Underground station where it occurs or is reported.",
        EX.Incident,
        EX.UndergroundStation,
    )
    add_object_property(
        graph,
        EX.stationHasAccessibilityAssessment,
        "station has accessibility assessment",
        "Relates a London Underground station to its wheelchair accessibility assessment.",
        EX.UndergroundStation,
        EX.WheelchairAccessibilityAssessment,
    )
    add_object_property(
        graph,
        EX.hasReplacementService,
        "has replacement service",
        "Relates a closure event to the bus replacement service provided during the disruption.",
        EX.ClosureEvent,
        EX.BusReplacementService,
    )
    add_object_property(
        graph,
        EX.replacementFollowsRoute,
        "replacement follows route",
        "Relates a bus replacement service to the route it follows.",
        EX.BusReplacementService,
        EX.UndergroundRoute,
    )
    add_object_property(
        graph,
        EX.usesRollingStockType,
        "uses rolling stock type",
        "Relates a London Underground line to the rolling stock type used on that line.",
        EX.UndergroundLine,
        EX.RollingStockType,
    )

    # Time-related object properties
    add_object_property(
        graph,
        EX.occursDuring,
        "occurs during",
        "Relates an event in the London Underground network to a temporal entity describing when it occurs.",
    )
    add_object_property(
        graph,
        EX.hasStartTime,
        "has start time",
        "Relates an event or temporal entity to its beginning in time.",
    )
    add_object_property(
        graph,
        EX.hasEndTime,
        "has end time",
        "Relates an event or temporal entity to its end in time.",
    )

    # ------------------------------------------------------------------
    # Datatype properties
    # ------------------------------------------------------------------
    add_datatype_property(
        graph,
        EX.stationName,
        "station name",
        "Stores the human-readable name of a London Underground station.",
        EX.UndergroundStation,
        XSD.string,
    )
    add_datatype_property(
        graph,
        EX.lineName,
        "line name",
        "Stores the human-readable name of a London Underground line.",
        EX.UndergroundLine,
        XSD.string,
    )
    add_datatype_property(
        graph,
        EX.fareZone,
        "fare zone",
        "Stores the TfL fare zone number of a London Underground station.",
        EX.UndergroundStation,
        XSD.integer,
    )
    add_datatype_property(
        graph,
        EX.routeName,
        "route name",
        "Stores the human-readable name of a London Underground route.",
        EX.UndergroundRoute,
        XSD.string,
    )
    add_datatype_property(
        graph,
        EX.incidentName,
        "incident name",
        "Stores the reported name or title of an incident in the London Underground network.",
        EX.Incident,
        XSD.string,
    )
    add_datatype_property(
        graph,
        EX.disruptionName,
        "disruption name",
        "Stores the reported name or title of a disruption event.",
        EX.DisruptionEvent,
        XSD.string,
    )

    add_datatype_property(
        graph,
        EX.officialAccessibilityStatus,
        "official accessibility status",
        "Stores the official accessibility designation assigned to a London Underground station.",
        EX.UndergroundStation,
        XSD.string,
    )
    add_datatype_property(
        graph,
        EX.isFullyWheelchairAccessible,
        "is fully wheelchair accessible",
        "Indicates whether a London Underground station is officially designated as fully wheelchair accessible.",
        EX.UndergroundStation,
        XSD.boolean,
    )

    add_datatype_property(
        graph,
        EX.operationalLengthMiles,
        "operational length in miles",
        "Stores the operational length of a London Underground line measured in miles.",
        EX.UndergroundLine,
        XSD.decimal,
    )
    add_datatype_property(
        graph,
        EX.currentStatus,
        "current status",
        "Stores the current operational status of a disruption event affecting the London Underground.",
        EX.DisruptionEvent,
        XSD.string,
    )
    add_datatype_property(
        graph,
        EX.delayMinutes,
        "delay in minutes",
        "Stores the delay caused by a delay event as a number of minutes.",
        EX.DelayEvent,
        XSD.integer,
    )
    add_datatype_property(
        graph,
        EX.severityLabel,
        "severity label",
        "Stores the reported severity level of an incident, such as Minor, Severe, or Suspended.",
        EX.Incident,
        XSD.string,
    )
    add_datatype_property(
        graph,
        EX.hasDelayDuration,
        "has delay duration",
        "Stores the duration of a delay event using an xsd:duration value.",
        EX.DelayEvent,
        XSD.duration,
    )

    add_datatype_property(
        graph,
        EX.inaugurationDate,
        "inauguration date",
        "Stores the inauguration date of a London Underground route.",
        EX.UndergroundRoute,
        XSD.date,
    )
    add_datatype_property(
        graph,
        EX.inaugurationYear,
        "inauguration year",
        "Stores the inauguration year of a London Underground route.",
        EX.UndergroundRoute,
        XSD.gYear,
    )

    add_datatype_property(
        graph,
        EX.replacementRouteName,
        "replacement route name",
        "Stores the name of a replacement route used by a bus replacement service.",
        EX.BusReplacementService,
        XSD.string,
    )
    add_datatype_property(
        graph,
        EX.closureReason,
        "closure reason",
        "Stores the reported reason for a closure event in the London Underground network.",
        EX.ClosureEvent,
        XSD.string,
    )

    add_datatype_property(
        graph,
        EX.maintenanceName,
        "maintenance name",
        "Stores the name or description of a maintenance event.",
        EX.MaintenanceEvent,
        XSD.string,
    )
    add_datatype_property(
        graph,
        EX.plannedStartDate,
        "planned start date",
        "Stores the planned start date of a maintenance event.",
        EX.MaintenanceEvent,
        XSD.date,
    )
    add_datatype_property(
        graph,
        EX.plannedEndDate,
        "planned end date",
        "Stores the planned end date of a maintenance event.",
        EX.MaintenanceEvent,
        XSD.date,
    )

    add_datatype_property(
        graph,
        EX.rollingStockName,
        "rolling stock name",
        "Stores the name of a rolling stock type used on the London Underground.",
        EX.RollingStockType,
        XSD.string,
    )
    add_datatype_property(
        graph,
        EX.standardPassengerCapacity,
        "standard passenger capacity",
        "Stores the standard passenger capacity of a rolling stock type.",
        EX.RollingStockType,
        XSD.integer,
    )

    # ------------------------------------------------------------------
    # Subproperty mappings. Keep only semantically safe mappings
    # ------------------------------------------------------------------
    graph.add((EX.stationHasAccessibilityAssessment, RDFS.subPropertyOf, TMFAC.accessibilityAssessment))

    graph.add((EX.hasStartTime, RDFS.subPropertyOf, TIME.hasBeginning))
    graph.add((EX.hasEndTime, RDFS.subPropertyOf, TIME.hasEnd))
    graph.add((EX.occursDuring, RDFS.subPropertyOf, TIME.hasTime))
    graph.add((EX.hasDelayDuration, RDFS.subPropertyOf, TIME.hasXSDDuration))

    # ------------------------------------------------------------------
    # Serialise
    # ------------------------------------------------------------------
    output_file = "ontologies/tbox_ontology.ttl"
    graph.serialize(destination=output_file, format="turtle")
    print(f"Ontology serialised to {output_file}")

if __name__ == "__main__":
    main()
