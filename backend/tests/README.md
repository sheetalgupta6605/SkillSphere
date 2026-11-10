# Backend test cases

| Case | Expected result | Current verification |
| --- | --- | --- |
| Normalize `JS` and `React` skills | Aliases become `javascript` and `react.js` | Passed in `test_resume.py` |
| Parse a resume with name/email/skills | Extracts only values present in the text | Passed in `test_resume.py` |
| Calculate a four-skill match with three matches | Returns `75` | Passed in `test_matching.py` |
| Calculate a match with no required skills | Returns `None`, without division error | Passed in `test_matching.py` |
| Build the FastAPI application | Imports successfully and registers API routes | Passed during validation |

MongoDB-backed authentication, uploads, and application workflows require the user's MongoDB connection and JWT secret before they can be run end-to-end.
