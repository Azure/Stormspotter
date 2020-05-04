# Roadmap

## Development
Stormspotter is developed and maintained primarily by the Azure Red Team (ART). This tool should be viewed as an independent tool used for security awareness and is not a Microsoft product or service. ART will maintain this tool as long as deemed feasible.

We encourage the community to work with us to help improve the functionality of this tool to support Azure security awareness for all.

## TODOs

Stormspotter is reimagining of a tool created internally in 2018. As such, there are many improvements to be made. Here are some immediate focuses:

### Core
- Refactor code that is shared between ingestor and dashboard

### Ingestor
- Rewrite the ingestor with `async` as opposed to current threading implementation. Testing against downloading 300k+ Service Principals took about an hour.
- Consider sqlite implementation vs current zipfile implementation for outputting data.
  
### Dashboard
- Add icons for all Azure resource types
- Add ability to expand nodes
- Consider rewriting frontend in React directly to make adding additional features easier.