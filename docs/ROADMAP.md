# Milestones

Step 3 corresponds to M0 Foundation in PRODUCT_SPEC section 19. It initializes the
repository, health API, Organic shell, database boundary, migrations, local
containers, dependency locks, and CI. Authentication is a deny-only seam.

The exact next milestone is **M1 Identity and customer core**: operator bootstrap,
local password hashing and opaque sessions, CSRF/Origin protection, workspace
memberships and staff roles, single-use setup links, portal identity bindings,
teams, scoped customer/contact CRUD, a basic customer screen, and two-workspace
plus same-customer/contact authorization tests. Implement these together before
exposing customer data. Session handling must not use browser localStorage.

M2 then adds the portal request → agent reply → resolution vertical slice.
M3 adds versioned configuration and follow-up. M4 adds events and analytics.
M5 adds knowledge and RAG. M6 adds rules-based health and product finishing.
M7 validates the full release, including restore, load, security, and accessibility
evidence. These are planned, not existing features. No deployment is part of Step 3.
