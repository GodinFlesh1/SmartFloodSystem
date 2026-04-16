Project overview:

The EcoFlood project addresses a critical gap in the UK's disaster response infrastructure: the "last-mile" communication of street-level flood risks. While national systems provide regional alerts, they often fail to account for hyper-local topographical accumulation points, leading to "warning fatigue" and delayed evacuation.

This computer-based solution integrates the Environment Agency’s Real-Time API with localized high-resolution terrain data. The backend, engineered with Python (FastAPI), features an asynchronous logic engine that calculates the velocity of rising water to detect flash-flood threats. The frontend, developed in Flutter (Web/PWA), visualizes these risks through interactive heatmaps. Data persistence and real-time state broadcasting are managed by Supabase (PostgreSQL/PostGIS), ensuring that life-critical notifications reach users with sub-second latency.

Project aims:

The primary aim is to engineer a high-performance, real-time early warning system that provides actionable, hyper-local flood intelligence to residents in high-risk zones.

Additional Aims:

Predictive Logic: To implement a velocity-based alerting algorithm ($\Delta h/\Delta t$) that differentiates between standard tides and dangerous flash-floods.

Geospatial Visualization: To visualize street-level "Blue-Spots" (accumulation points) using an interactive Mapbox/Google Maps overlay.

System Reliability: To utilize Supabase’s Realtime engine to ensure reliable, low-latency delivery of emergency SMS and push notifications.

Accessibility & Inclusivity: To design a WCAG 2.1 compliant interface that is highly legible and functional for diverse user groups during emergency stress.

Project deliverable(s):

To achieve the project aims, the following technical artefacts will be produced:

Frontend (Flutter Web/PWA): A responsive dashboard utilizing the Maps_flutter package. It will feature custom GeoJSON layers for flood risk polygons and a "Safe-Route" navigation feature.

Backend (Python FastAPI): A microservice responsible for the automated ingestion of hydrometric data. It will perform mathematical transformations to calculate the rate of rise and trigger threshold events.

Database (Supabase/PostGIS): A PostgreSQL instance leveraging PostGIS for complex spatial queries, determining if a user's location intersects with predicted flood zones.

Engineering Approaches: The project follows an Agile (Scrum) methodology with 2-week sprints. Test-Driven Development (TDD) will be used for the alert-trigger logic to ensure safety-critical reliability. Version control will be managed via Git/GitHub.

Alternatives: MongoDB was considered for its flexible schema; however, Supabase was selected for its superior Realtime engine and native PostGIS support, which are essential for precise geographical safety applications.