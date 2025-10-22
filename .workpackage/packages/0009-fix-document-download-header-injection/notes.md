# Fix document download header injection

Owner: jkropp
Status: done
Created: 2025-10-22T04:50:01.152Z

---
- 2025-10-22T04:50:16.656Z • jkropp: Investigating filename sanitisation and response header construction in documents download flow.
- 2025-10-22T04:57:11.947Z • jkropp: Sanitised stored filenames, added safe Content-Disposition builder, and regression tests covering header injection scenarios.
