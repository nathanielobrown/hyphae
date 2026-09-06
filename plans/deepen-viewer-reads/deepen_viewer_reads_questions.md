# Set the page-read seam and its tests

## 1. Should each page dependency return rendered markup or a typed page model?

Today each endpoint parses query parameters, opens the Store, binds a query, maps raw rows, records citations, calls page markup, and wraps the result in a response. A FastAPI dependency can depend on the Viewer and page-specific parameter dependencies, do that work with a short Store open, and return either rendered markup or the typed values that markup needs.


| Option           | Shape                                                                     | Trade-off                                                                                          |
| ---------------- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Rendered markup  | The endpoint receives finished markup and wraps it in the Viewer response | Smallest endpoint interface and greatest depth; the page read module owns the full page assembly   |
| Typed page model | The endpoint receives page data and passes it to markup                   | Keeps reading and rendering distinct, but leaves each endpoint knowing the markup interface        |
| Response         | The dependency returns the FastAPI response itself                        | Smallest endpoint body, but the page module becomes tied to FastAPI and the endpoint adds no value |


The choice sets the interface for every page and will be costly to reverse after tests and dependencies settle around it.

### Recommendation: Return rendered markup

This gives callers the most leverage and keeps the Store, raw rows, query bindings, citations, and markup assembly inside one deep page module. We give up a separate typed page model that no second caller needs today.

### User Response:

Have one dependency that returns typed model and another that takes that and turns it into markup. That way a route can use whatever makes most sense and we've separate the layers

## 2. Should tests stay at the URL seam or also call page dependencies directly?

The current viewer suite drives real fixture stores through FastAPI URLs and checks rendered behavior. The refactor can preserve that interface while moving work behind dependencies. Direct dependency tests would expose the new internal shape as another test surface; URL tests would let the implementation change without rewriting tests.

Two choices fit. Keep URL behavior as the only test seam and add cases only where pagination or validation lacks coverage. Or treat each page dependency as a second test seam and assert its return value directly.

The wrong choice either leaves dependency composition unguarded or makes an internal refactor break tests that users would never notice.

### Recommendation: Keep the URL as the test seam

Test parameter dependencies through the URLs that invoke them, using the recorded fixture stores. Keep the existing source-tree checks for import direction, but don't add direct tests for page-read internals. We give up pinpoint dependency tests in exchange for tests that survive another deepening.

### User Response:

Keep the URL as the test seam

## 3. Should pagination dependencies share primitives or one universal pagination model?

The node children log, session list, records page, and offload page all paginate, but they do not mean the same thing: two use numbered pages, records use a line cursor, and offloads use a character offset. Their defaults and ceilings also differ. FastAPI dependencies can still compose small checks where the semantics match.

Two choices fit. Page-specific parameter dependencies can depend on shared validators for positive page numbers and bounded sizes. A universal pagination model can carry page, cursor, offset, and size for every route, leaving most fields meaningless on each page.

A universal model would widen every caller's interface. Page-specific dependencies repeat a little declaration but preserve each URL's meaning.

### Recommendation: Share validators, not a universal pagination model

Compose page-specific dependencies from the checks they truly share. Keep defaults and URL meanings with each page. We give up one nominal type across all routes, because it would be shallow.

### User Response:

Share wherever it makes sense. If things can be consolidated, consolidate. If not, keep separate

## Pending questions (depends on answers above)

- Should missing rows become dependency refusals or values the endpoint translates? — depends on Q1
- Which page should be the first vertical slice? — depends on Q1, Q2



# Place the typed models and set the reach



## 4. Should the typed model between read and markup dependencies live in a neutral models module?

The earlier viewer layout plan keeps a view-model beside the markup function that consumes it and rejects a `models.py` when markup has only one reader. Your answer to Q1 creates a stronger seam: one dependency produces a typed page model and a second dependency consumes it to produce markup. Keeping the type in the markup module would make the read dependency import the implementation on the other side of that seam.

Two choices fit. Put each aggregate page model in a neutral `models.py` imported by both dependencies, while leaving markup-only row types beside markup. Or keep every type in markup and accept that the read dependency reaches into the markup module for its return type.

This either sharpens the separation you asked for or preserves the earlier layout decision. Moving a handful of types later is cheap, but letting every page choose differently will weaken locality.

### Recommendation: Add a neutral model only where the dependency seam needs one

Use `models.py` for the aggregate value passed from reading to markup. Keep types that only markup reads beside markup. We give up the old rule’s absolute simplicity to keep the new seam honest.

### User Response:

Agree with recommendation

## 5. Should the two-dependency chain cover fragments as well as full documents?

The node page package serves full documents plus expansions, details, enrichment lines, and popovers. Those fragment routes account for many raw Store reads from the report, but several return one short markup value rather than a page. Applying the same read-model-to-markup chain everywhere would remove all raw rows from endpoints; it would also add a model where a fragment currently needs one value.

Two choices fit. Use the chain for full documents and for fragments whose read or markup is shared, leaving trivial fragments with one dependency. Or require both dependencies for every route that reads the Store.

The broad rule removes more leakage. The selective rule avoids shallow models and follows your Q3 answer: consolidate only where the meaning is shared.

### Recommendation: Use the chain where it adds depth

Cover every full document. For fragments, split reading from markup when either side has real behavior or reuse; let a trivial fragment dependency return markup directly. We give up a uniform mechanical rule to avoid shallow modules.

### User Response:

Agree with recommendation

## Pending questions (depends on answers above)

- None if Q4 and Q5 follow the recommendations; missing rows can remain FastAPI refusals in the read dependency, and implementation can proceed by one page at a time

