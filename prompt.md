# Task Prompt: Frontend Audit, Debugging & Fixes

You are a senior frontend engineer and debugging agent.

The project currently has MANY errors and broken functionality in the frontend. Your task is to thoroughly inspect the entire frontend, identify every issue you can find, fix them, and verify that the application works correctly.

IMPORTANT:
Do NOT just fix the first error you encounter. Perform a complete frontend audit and continue until the frontend is stable.

## 1. Inspect the project first

Before changing anything:

- Understand the complete project structure.
- Identify the frontend framework and technology stack.
- Inspect package.json and all frontend configuration files.
- Inspect all pages, components, hooks, utilities, services, API integrations, routes, state management, and styling files.
- Understand how the frontend communicates with the backend.
- Identify existing architectural patterns and preserve them where possible.

## 2. Run the application

Start the frontend using the appropriate existing command.

Check:

- Compilation errors
- Runtime errors
- Browser console errors
- Network/API errors
- Failed requests
- Broken routes
- React/JS/TypeScript warnings
- Missing dependencies
- Invalid imports/exports
- Undefined variables/functions
- Component rendering failures

Do not assume an error is harmless. Investigate its root cause.

## 3. Fix ALL frontend errors

Systematically check and fix:

### Code
- Syntax errors
- TypeScript errors
- JavaScript errors
- Incorrect imports/exports
- Undefined variables
- Incorrect function calls
- Incorrect props
- Incorrect state updates
- Hook dependency problems
- Async/await issues
- Null/undefined handling
- Incorrect event handlers

### Components
- Components that fail to render
- Incorrect component composition
- Broken props
- Missing keys in lists
- Incorrect conditional rendering
- Loading-state problems
- Empty-state problems
- Error-state problems

### Routing
Check every route:

- Correct route configuration
- Navigation
- Protected routes
- Route parameters
- 404 handling
- Refreshing a route directly
- Back/forward navigation

### API / Backend Integration

Inspect every frontend API call.

Verify:

- Correct API URLs
- Correct HTTP methods
- Correct request body
- Correct headers
- Authentication handling
- Response parsing
- Error handling
- Loading states
- Timeout/failure handling
- Environment variables

Do NOT replace real backend functionality with fake/mock data just to remove errors.

If the backend API contract is unclear, inspect the backend implementation and determine the correct contract from the actual code.

### UI / UX

Check every page for:

- Broken layouts
- Overlapping elements
- Incorrect spacing
- Missing elements
- Broken buttons
- Broken forms
- Incorrect navigation
- Bad responsive behavior
- Mobile layout problems
- Desktop layout problems
- Overflow issues
- Missing loading indicators
- Poor error messages

Preserve the existing visual design unless changing it is necessary to fix functionality.

## 4. Test every major user flow

After fixing the code, test the application as a real user.

Verify flows such as:

1. Opening the application
2. Navigation between pages
3. Forms
4. Buttons
5. Authentication if present
6. API requests
7. Data loading
8. Data creation/update/deletion if present
9. Error states
10. Empty states
11. Page refresh
12. Responsive layouts

Do not assume something works just because the code compiles.

## 5. Check the console and network

After fixing the frontend:

- Re-open the application.
- Check browser console.
- Check network requests.
- Identify remaining errors/warnings.
- Fix genuine problems instead of suppressing them.

Do NOT use hacks such as:

- Disabling ESLint rules unnecessarily
- Ignoring TypeScript errors
- Suppressing console errors
- Adding arbitrary try/catch blocks without fixing the cause
- Commenting out broken functionality
- Replacing functionality with dummy data

## 6. Build and validate

Run the project's appropriate:

- npm/pnpm/yarn install if required
- lint
- type-check
- tests
- production build

Fix every error produced by these checks.

Then run the application again and verify the result.

## 7. Maintainability

While fixing the application:

- Keep the existing architecture where reasonable.
- Avoid unnecessary rewrites.
- Avoid duplicate code.
- Use reusable components where appropriate.
- Keep naming consistent.
- Remove dead/broken code only when safe.
- Do not introduce unnecessary dependencies.

## 8. Final verification

Before finishing, perform one final complete frontend audit.

The final state must satisfy:

- Frontend starts successfully.
- No compilation errors.
- No unresolved runtime errors.
- No broken major routes.
- No broken major interactions.
- API integrations work correctly.
- Forms work correctly.
- Responsive UI works correctly.
- Production build succeeds.
- Existing functionality is preserved.

## 9. Create/update documentation

Create or update:

`FRONTEND_FIXES.md`

Document:

- Problems discovered
- Root causes
- Fixes implemented
- Important files changed
- API issues discovered
- Validation/testing performed
- Build/lint/test results
- Any remaining issue that genuinely requires backend/external configuration

Also create/update:

`prompt.md`

This file should contain the original task requirements and the instructions used to guide the implementation.
