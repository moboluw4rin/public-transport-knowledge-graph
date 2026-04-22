"""
London Underground Knowledge Graph - SPARQL Query Executor.

This script loads the full knowledge graph from the Turtle
file and executes a series of SPARQL queries to extract insights.

The results of each query are logged to a text file in a readable format.

The queries cover various aspects of the London Underground system,
including station accessibility, line disruptions, interchange stations,
and more. This serves as a demonstration of how to interact with the RDF
graph using SPARQL and can be easily extended with additional queries
as needed.
"""

# pylint: disable=C0301

from pathlib import Path
import rdflib

def run_queries():
    """Load the RDF graph and execute predefined SPARQL queries."""
    basePath = Path(__file__).parent # pylint: disable=C0103
    ttl_path = basePath / "ontologies" / "full_knowledge_graph.ttl"
    log_path = basePath / "queries" /  "sparql_results.txt"

    # 1. Initialise the graph and parse the Turtle file
    g = rdflib.Graph()
    try:
        g.parse(ttl_path, format="turtle")
    except Exception as e: # pylint: disable=W0718
        print(f"Failed to load graph: {e}")
        return

    # 2. Define standard prefixes
    prefixes = """
    PREFIX ex:   <http://example.org/ontology-express#>
    PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
    PREFIX time: <http://www.w3.org/2006/time#>
    """

    # 3. Store queries in a dictionary
    queries_dict = {
        "Fully wheelchair accessible stations": prefixes + """
            SELECT ?station ?stationName
            WHERE {
                ?station a ex:UndergroundStation ;
                        ex:stationName ?stationName ;
                        ex:isFullyWheelchairAccessible true .
            }
            ORDER BY ?stationName
        """,

        "Total operational length of the Circle Line": prefixes + """
            SELECT ?lengthMiles
            WHERE {
            ?line a ex:UndergroundLine ;
                    ex:lineName "Circle"^^xsd:string ;
                    ex:operationalLengthMiles ?lengthMiles .
            }
        """,

        "Transport disruptions affecting the Piccadilly Line": prefixes + """
            SELECT ?disruption ?disruptionName ?status
            WHERE {
                { ?disruption a ex:DisruptionEvent }
                UNION { ?disruption a ex:ClosureEvent }
                UNION { ?disruption a ex:DelayEvent }
                ?disruption ex:affectsLine ?line ;
                            ex:disruptionName ?disruptionName ;
                            ex:currentStatus ?status .
                ?line ex:lineName "Piccadilly"^^xsd:string .
            }
        """,

        "Total number of stations affected by each disruption event": prefixes + """
            SELECT ?disruption ?disruptionName (COUNT(DISTINCT ?station) AS ?stationCount)
            WHERE {
                { ?disruption a ex:DisruptionEvent }
                UNION { ?disruption a ex:ClosureEvent }
                UNION { ?disruption a ex:DelayEvent }
                ?disruption ex:disruptionName ?disruptionName ;
                            ex:occursAtStation ?station .
                ?station a ex:UndergroundStation .
            }
            GROUP BY ?disruption ?disruptionName
            ORDER BY DESC(?stationCount)
        """,

        "Interchange points between the District Line and Bakerloo Line": prefixes + """
            SELECT ?station ?stationName
            WHERE {
            ?station a ex:InterchangeStation ;
                    ex:stationName ?stationName ;
                    ex:servedByLine ?line1, ?line2 .
            ?line1 ex:lineName "District"^^xsd:string .
            ?line2 ex:lineName "Bakerloo"^^xsd:string .
            }
            ORDER BY ?stationName
        """,

        "Stations in Zone 1": prefixes + """
            SELECT DISTINCT ?station ?stationName
            WHERE {
                ?station a ex:UndergroundStation ;
                        ex:stationName ?stationName ;
                        ex:fareZone 1 .
            }
            ORDER BY ?stationName
        """,

        "Transport routes inaugurated before the year 1989": prefixes + """
            SELECT ?route ?routeName ?inaugYear
            WHERE {
                ?route a ex:UndergroundRoute ;
                    ex:routeName ?routeName ;
                    ex:inaugurationYear ?inaugYear .
                FILTER (STR(?inaugYear) < "1989")
            }
            ORDER BY ?inaugYear
        """,

        "Stations served by more than two Underground lines": prefixes + """
            SELECT ?station ?stationName (COUNT(DISTINCT ?line) AS ?lineCount)
            WHERE {
                ?station a ex:UndergroundStation ;
                        ex:stationName ?stationName ;
                        ex:servedByLine ?line .
                ?line a ex:UndergroundLine .
            }
            GROUP BY ?station ?stationName
            HAVING (COUNT(DISTINCT ?line) > 2)
            ORDER BY DESC(?lineCount) ?stationName
        """,

        "Stations affected by both a disruption and a scheduled maintenance event": prefixes + """
            SELECT DISTINCT ?station ?stationName
            WHERE {
                ?station a ex:UndergroundStation ;
                        ex:stationName ?stationName .
                { ?disruption a ex:DisruptionEvent }
                UNION { ?disruption a ex:ClosureEvent }
                UNION { ?disruption a ex:DelayEvent }
                ?disruption ex:occursAtStation ?station .
                ?maintenance a ex:MaintenanceEvent ;
                            ex:occursAtStation ?station .
                FILTER (?disruption != ?maintenance)
            }
            ORDER BY ?stationName
        """,

        "Standard passenger capacity of the rolling stock used on the Victoria Line": prefixes + """
            SELECT ?lineName ?stockName ?capacity
            WHERE {
                ?line a ex:UndergroundLine ;
                    ex:lineName ?lineName ;
                    ex:usesRollingStockType ?stock .
                ?stock ex:rollingStockName ?stockName ;
                    ex:standardPassengerCapacity ?capacity .
                FILTER (?lineName = "Victoria"^^xsd:string)
            }
        """,

        "Stations with step-free access but not full wheelchair access": prefixes + """
            SELECT ?station ?stationName ?accessibilityStatus
            WHERE {
                ?station a ex:UndergroundStation ;
                        ex:stationName ?stationName ;
                        ex:isFullyWheelchairAccessible false ;
                        ex:officialAccessibilityStatus ?accessibilityStatus .
                FILTER (CONTAINS(LCASE(STR(?accessibilityStatus)), "step-free"))
            }
            ORDER BY ?stationName
        """,

        "Lines sharing at least one interchange station with the Victoria Line": prefixes + """
            SELECT DISTINCT ?otherLineName
            WHERE {
                ?station a ex:InterchangeStation ;
                        ex:interchangesWithLine ?victoriaLine ;
                        ex:interchangesWithLine ?otherLine .
                ?victoriaLine ex:lineName "Victoria"^^xsd:string .
                ?otherLine ex:lineName ?otherLineName .
                FILTER (?otherLineName != "Victoria"^^xsd:string)
            }
        """,

        "Disruption events affected more than one Underground line at the same time": prefixes + """
            SELECT ?disruption ?disruptionName (COUNT(DISTINCT ?line) AS ?lineCount)
            WHERE {
                { ?disruption a ex:DisruptionEvent }
                UNION { ?disruption a ex:ClosureEvent }
                UNION { ?disruption a ex:DelayEvent }
                ?disruption ex:disruptionName ?disruptionName ;
                            ex:affectsLine ?line .
            }
            GROUP BY ?disruption ?disruptionName
            HAVING (COUNT(DISTINCT ?line) > 1)
        """,

        "Stations affected by the current closure event on the Piccadilly Line": prefixes + """
            SELECT DISTINCT ?station ?stationName ?closureName
            WHERE {
                ?closure a ex:ClosureEvent ;
                        ex:disruptionName ?closureName ;
                        ex:primaryLine ?line ;
                        ex:occursAtStation ?station ;
                        ex:currentStatus ?status .
                FILTER(CONTAINS(LCASE(STR(?status)), "suspended") || CONTAINS(LCASE(STR(?status)), "closure"))
                ?line ex:lineName "Piccadilly"^^xsd:string .
                ?station a ex:UndergroundStation ;
                        ex:stationName ?stationName .
            }
        """,

        "Underground lines have no reported disruptions at the current time": prefixes + """
            SELECT DISTINCT ?line ?lineName
            WHERE {
                ?line a ex:UndergroundLine ;
                    ex:lineName ?lineName .
                FILTER NOT EXISTS {
                    ?disruption a ex:DisruptionEvent ;
                                ex:affectsLine ?line ;
                                ex:currentStatus ?status .
                    FILTER(LCASE(STR(?status)) = "active")
                }
            }
        """,

        "Rolling stock types used exclusively by a single Underground line": prefixes + """
            SELECT ?stock ?stockName (COUNT(DISTINCT ?line) AS ?lineCount)
            WHERE {
                ?stock a ex:RollingStockType ;
                    ex:rollingStockName ?stockName .
                ?line a ex:UndergroundLine ;
                    ex:usesRollingStockType ?stock .
            }
            GROUP BY ?stock ?stockName
            HAVING (COUNT(DISTINCT ?line) = 1)
        """,

        "Stations that are endpoints": prefixes + """
            SELECT DISTINCT ?station ?stationName
            WHERE {
                ?station a ex:UndergroundStation ;
                        ex:stationName ?stationName ;
                        ex:servedByLine ?line .
                FILTER NOT EXISTS { ?station a ex:InterchangeStation }
            }
            GROUP BY ?station ?stationName
            HAVING (COUNT(DISTINCT ?line) = 1)
            ORDER BY ?stationName
        """,

        "Routes inaugurated before 1989 still currently operational": prefixes + """
            SELECT ?route ?routeName ?inaugYear
            WHERE {
                ?route a ex:UndergroundRoute ;
                    ex:routeName ?routeName ;
                    ex:inaugurationYear ?inaugYear .
                ?line ex:lineHasRoute ?route ;
                    ex:currentStatus ?lineStatus .
                FILTER (STR(?inaugYear) < "1989")
                FILTER(LCASE(STR(?lineStatus)) = "active")
            }
            ORDER BY ?inaugYear ?routeName
        """,

        "Incidents classified with severity level Severe": prefixes + """
            SELECT ?incident ?station ?stationName
            WHERE {
                { ?incident a ex:DisruptionEvent }
                UNION { ?incident a ex:ClosureEvent }
                UNION { ?incident a ex:DelayEvent }
                ?incident ex:severityLabel ?severity ;
                        ex:occursAtStation ?station .
                ?station ex:stationName ?stationName .
                FILTER(CONTAINS(LCASE(STR(?severity)), "severe"))
            }
        """,

        "Which stations have accessibility limitations and are also affected by current disruptions?": prefixes + """
            SELECT DISTINCT ?station ?stationName ?disruptionName
            WHERE {
                    ?station a ex:UndergroundStation ;
                                    ex:stationName ?stationName .
                    OPTIONAL { ?station ex:isFullyWheelchairAccessible ?wheelchair . }
                    OPTIONAL { ?station ex:officialAccessibilityStatus ?accessStatus . }
                    FILTER(
                        (BOUND(?wheelchair) && ?wheelchair = false)
                        || (BOUND(?accessStatus) && CONTAINS(LCASE(STR(?accessStatus)), "step-free"))
                        || (BOUND(?accessStatus) && CONTAINS(LCASE(STR(?accessStatus)), "limited"))
                    )
                    { ?disruption a ex:DisruptionEvent }
                    UNION { ?disruption a ex:ClosureEvent }
                    UNION { ?disruption a ex:DelayEvent }
                    ?disruption ex:occursAtStation ?station ;
                                ex:disruptionName ?disruptionName .
            }
        """
    }

    # 4. Open file and execute queries
    with open(log_path, "w", encoding="utf-8") as f:
        for query_name, sparql_query in queries_dict.items():
            f.write(f"{'='*80}\nExecuting: {query_name}\n{'-'*80}\n")
            try:
                results = g.query(sparql_query)
                vars_list = results.vars

                if not vars_list:
                    f.write("No variables returned.\n\n")
                    continue

                # Format headers
                header_row = " | ".join([str(var).ljust(30) for var in vars_list])
                f.write(header_row + "\n")
                f.write("-" * len(header_row) + "\n")

                # Format each result row
                count = 0
                for row in results:
                    count += 1
                    row_strs = []
                    for val in row:
                        if val is None:
                            row_strs.append("NULL".ljust(30))
                        else:
                            val_str = str(val)
                            # Clean URIs for logging
                            if isinstance(val, rdflib.URIRef):
                                val_str = val_str.rsplit('#', maxsplit=1)[-1].split('/')[-1]
                            row_strs.append(val_str.ljust(30))
                    f.write(" | ".join(row_strs) + "\n")

                f.write(f"\nTotal Results: {count}\n\n")

            except Exception as e: # pylint: disable=W0718
                f.write(f"Error executing query:\n{e}\n\n")

    print(f"Query execution complete. Results logged to: {log_path}")

if __name__ == "__main__":
    run_queries()
