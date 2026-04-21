from pathlib import Path
import rdflib

def run_queries():
    basePath = Path(__file__).parent
    ttl_path = basePath / "ontologies" / "full_knowledge_graph.ttl"
    log_path = basePath /  "sparql_log.txt"

    # 1. Initialize the graph and parse the Turtle file
    g = rdflib.Graph()
    try:
        g.parse(ttl_path, format="turtle")
    except Exception as e:
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
        "CQ-OZE-1: Fully wheelchair accessible stations": prefixes + """
            SELECT ?station ?stationName
            WHERE {
                ?station a ex:UndergroundStation ;
                         ex:stationName ?stationName ;
                         ex:isFullyWheelchairAccessible true .
            }
            ORDER BY ?stationName
        """,
        "CQ-OZE-2: Total operational length of Circle Line": prefixes + """
            SELECT ?lengthMiles
            WHERE {
              ?line a ex:UndergroundLine ;
                     ex:lineName "Circle"^^xsd:string ;
                     ex:operationalLengthMiles ?lengthMiles .
            }
        """,
        "CQ-OZE-3: Current disruptions on Piccadilly Line": prefixes + """
            SELECT ?disruption ?disruptionName ?status
            WHERE {
                ?disruption a ex:DisruptionEvent ;
                            ex:affectsLine ?line ;
                            ex:disruptionName ?disruptionName ;
                            ex:currentStatus ?status .
                ?line ex:lineName "Piccadilly"^^xsd:string .
                FILTER(LCASE(STR(?status)) = "active")
            }
        """,
        "CQ-OZE-4: Delay duration of signal failure at Victoria": prefixes + """
            SELECT DISTINCT ?delayEvent ?minutes
            WHERE {
              ?delayEvent a ex:DelayEvent ;
                          ex:occursAtStation ?station ;
                          ex:delayMinutes ?minutes ;
                          ex:disruptionName ?name .
              ?station ex:stationName "Victoria Station"^^xsd:string .   
              FILTER(CONTAINS(LCASE(STR(?name)), "signal failure"))
            }
        """,
        "CQ-OZE-5: Interchange points between District and Bakerloo": prefixes + """
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
        "CQ-OZE-6: Severity level at King's Cross St. Pancras": prefixes + """
            SELECT ?incident ?severity
            WHERE {
                ?incident a ex:Incident ;
                          ex:incidentName ?incidentName ;
                          ex:severityLabel ?severity ;
                          ex:occursAtStation ?station .
                ?station ex:stationName "King's Cross St. Pancras"^^xsd:string .
            }
        """,
        "CQ-OZE-7: Routes inaugurated before 1989": prefixes + """
            SELECT ?route ?routeName ?inaugYear
            WHERE {
                ?route a ex:UndergroundRoute ;
                       ex:routeName ?routeName ;
                       ex:inaugurationYear ?inaugYear .
                FILTER (?inaugYear < "1989"^^xsd:gYear)
            }
            ORDER BY ?inaugYear
        """,
        "CQ-OZE-8: Replacement bus for Caledonian Road Station": prefixes + """
            SELECT ?replacementService ?replacementRouteName
            WHERE {
                ?closure a ex:ClosureEvent ;
                         ex:occursAtStation ?station ;
                         ex:hasReplacementService ?replacementService .
                ?station ex:stationName "Caledonian Road Station"^^xsd:string .
                ?replacementService ex:replacementRouteName ?replacementRouteName .
            }
        """,
        "CQ-OZE-9: Maintenance between September and December": prefixes + """
            SELECT ?maintenance ?maintenanceName ?startDate ?endDate
            WHERE {
                ?maintenance a ex:MaintenanceEvent ;
                             ex:maintenanceName ?maintenanceName ;
                             ex:plannedStartDate ?startDate ;
                             ex:plannedEndDate ?endDate .
                FILTER(MONTH(?startDate) >= 9 && MONTH(?startDate) <= 12)
            }
            ORDER BY ?startDate
        """,
        "CQ-OZE-10: Passenger capacity of Victoria Line stock": prefixes + """
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
        "CQ-ALD-1: Step-free access but not full wheelchair access": prefixes + """
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
        "CQ-ALD-2: Interchanges shared with Victoria Line": prefixes + """
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
        "CQ-ALD-3: Disruptions affecting multiple lines": prefixes + """
            SELECT ?disruption ?disruptionName (COUNT(DISTINCT ?line) AS ?lineCount)
            WHERE {
                ?disruption a ex:DisruptionEvent ;
                            ex:disruptionName ?disruptionName ;
                            ex:affectsLine ?line .
            }
            GROUP BY ?disruption ?disruptionName
            HAVING (COUNT(DISTINCT ?line) > 1)
        """,
        "CQ-ALD-4: Stations affected by current Piccadilly closure": prefixes + """
            SELECT DISTINCT ?station ?stationName ?closureName
            WHERE {
                ?closure a ex:ClosureEvent ;
                         ex:disruptionName ?closureName ;
                         ex:affectsLine ?line ;
                         ex:occursAtStation ?station ;
                         ex:currentStatus "Active"^^xsd:string .
                ?line ex:lineName "Piccadilly"^^xsd:string .
                ?station a ex:UndergroundStation ;
                         ex:stationName ?stationName .
            }
        """,
        "CQ-ALD-5: Replacement buses for this month's closures": prefixes + """
            SELECT ?closure ?closureName ?replacementService ?replacementRouteName ?startDate
            WHERE {
                ?closure a ex:ClosureEvent ;
                         ex:disruptionName ?closureName ;
                         ex:hasReplacementService ?replacementService ;
                         ex:plannedStartDate ?startDate .
                ?replacementService ex:replacementRouteName ?replacementRouteName .
                FILTER (MONTH(?startDate) = MONTH(NOW()) && YEAR(?startDate) = YEAR(NOW()))
            }
        """,
        "CQ-ALD-6: Lines using Victoria Line's rolling stock": prefixes + """
            SELECT DISTINCT ?otherLineName ?stockName
            WHERE {
                ?victoriaLine a ex:UndergroundLine ;
                              ex:lineName "Victoria"^^xsd:string ;
                              ex:usesRollingStockType ?stock .
                ?otherLine a ex:UndergroundLine ;
                           ex:lineName ?otherLineName ;
                           ex:usesRollingStockType ?stock .
                ?stock ex:rollingStockName ?stockName .
                FILTER (?otherLineName != "Victoria"^^xsd:string)
            }
        """,
        "CQ-ALD-7: October maintenance schedules": prefixes + """
            SELECT ?maintenance ?maintenanceName ?startDate ?endDate
            WHERE {
                ?maintenance a ex:MaintenanceEvent ;
                             ex:maintenanceName ?maintenanceName ;
                             ex:plannedStartDate ?startDate ;
                             ex:plannedEndDate ?endDate .
                FILTER (MONTH(?startDate) = 10)
            }
            ORDER BY ?startDate ?maintenanceName
        """,
        "CQ-ALD-8: Pre-1989 operational routes": prefixes + """
            SELECT ?route ?routeName ?inaugYear
            WHERE {
                ?route a ex:UndergroundRoute ;
                       ex:routeName ?routeName ;
                       ex:inaugurationYear ?inaugYear .
                ?line ex:lineHasRoute ?route ;
                      ex:currentStatus ?lineStatus .
                FILTER (?inaugYear < "1989"^^xsd:gYear)
                FILTER(LCASE(STR(?lineStatus)) = "active")
            }
            ORDER BY ?inaugYear ?routeName
        """,
        "CQ-ALD-9: Severe incidents at stations": prefixes + """
            SELECT ?incident ?station ?stationName
            WHERE {
                ?incident a ex:Incident ;
                          ex:severityLabel "Severe"^^xsd:string ;
                          ex:occursAtStation ?station .
                ?station ex:stationName ?stationName .
            }
        """,
        "CQ-ALD-10: Avg delay for signal failures": prefixes + """
            SELECT (AVG(?minutes) AS ?averageDelay)
            WHERE {
                ?delay a ex:DelayEvent ;
                       ex:occursAtStation ?station ;
                       ex:delayMinutes ?minutes ;
                       ex:disruptionName ?name .
                ?station a ex:UndergroundStation .
                FILTER(CONTAINS(LCASE(STR(?name)), "signal failure"))
            }
        """,
        "CQ-ATH-1: Stations served by >2 lines": prefixes + """
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
        "CQ-ATH-2: Lines with no active disruptions": prefixes + """
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
        "CQ-ATH-3: Stations with disruption and maintenance": prefixes + """
            SELECT DISTINCT ?station ?stationName
            WHERE {
                ?station a ex:UndergroundStation ;
                         ex:stationName ?stationName .
                ?disruption a ex:DisruptionEvent ;
                            ex:occursAtStation ?station .
                ?maintenance a ex:MaintenanceEvent ;
                             ex:occursAtStation ?station .
                FILTER (?disruption != ?maintenance)
            }
            ORDER BY ?stationName
        """,
        "CQ-ATH-4: Total stations affected by each disruption": prefixes + """
            SELECT ?disruption ?disruptionName (COUNT(DISTINCT ?station) AS ?stationCount)
            WHERE {
                ?disruption a ex:DisruptionEvent ;
                            ex:disruptionName ?disruptionName ;
                            ex:occursAtStation ?station .
                ?station a ex:UndergroundStation .
            }
            GROUP BY ?disruption ?disruptionName
            ORDER BY DESC(?stationCount)
        """,
        "CQ-ATH-5: Overlapping maintenance events": prefixes + """
            SELECT ?event1 ?name1 ?start1 ?end1 ?event2 ?name2 ?start2 ?end2
            WHERE {
                ?event1 a ex:MaintenanceEvent ;
                    ex:maintenanceName ?name1 ;
                    ex:plannedStartDate ?start1 ;
                    ex:plannedEndDate ?end1 .
                ?event2 a ex:MaintenanceEvent ;
                    ex:maintenanceName ?name2 ;
                    ex:plannedStartDate ?start2 ;
                    ex:plannedEndDate ?end2 .
                FILTER (?event1 != ?event2)
                FILTER (?start1 <= ?end2 && ?start2 <= ?end1)
                FILTER (STR(?event1) < STR(?event2))
            }
            ORDER BY ?name1 ?name2
        """,
        "CQ-ATH-6: Stations with access limits & disruptions": prefixes + """
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
                    ?disruption a ex:DisruptionEvent ;
                                                    ex:occursAtStation ?station ;
                                                    ex:disruptionName ?disruptionName ;
                                                    ex:currentStatus "Active"^^xsd:string .
            }
        """,
        "CQ-ATH-7: Rolling stock exclusive to one line": prefixes + """
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
        "CQ-ATH-8: Endpoints (served by one line, not interchanges)": prefixes + """
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
        "CQ-ATH-9: Lines sharing closure reasons": prefixes + """
            SELECT ?reason ?line1Name ?line2Name
            WHERE {
                ?closure1 a ex:ClosureEvent ;
                          ex:closureReason ?reason ;
                          ex:affectsLine ?line1 .
                ?closure2 a ex:ClosureEvent ;
                          ex:closureReason ?reason ;
                          ex:affectsLine ?line2 .
                ?line1 ex:lineName ?line1Name .
                ?line2 ex:lineName ?line2Name .
                FILTER (?closure1 != ?closure2)
                FILTER (STR(?line1) < STR(?line2))
            }
        """,
        "CQ-ATH-10: Stations in Zone 1": prefixes + """
            SELECT DISTINCT ?station ?stationName
            WHERE {
                ?station a ex:UndergroundStation ;
                         ex:stationName ?stationName ;
                         ex:fareZone 1 .
            }
            ORDER BY ?stationName
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
                                val_str = val_str.split('#')[-1].split('/')[-1]
                            row_strs.append(val_str.ljust(30))
                    f.write(" | ".join(row_strs) + "\n")
                
                f.write(f"\nTotal Results: {count}\n\n")
                
            except Exception as e:
                f.write(f"Error executing query:\n{e}\n\n")

    print(f"Query execution complete. Results logged to: {log_path}")

if __name__ == "__main__":
    run_queries()