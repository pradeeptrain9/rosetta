      *> INSPECT in its three common shapes.
      *> Gotcha 1: INSPECT TALLYING ADDS to the counter. It does not reset
      *>           it first, so a counter reused across two INSPECTs
      *>           accumulates both counts.
      *> Gotcha 2: TALLYING FOR LEADING stops at the first non-matching
      *>           character, which is not the same as counting all of them.
      *> Gotcha 3: the field is fixed width, so trailing spaces from the
      *>           PIC X(20) padding are part of what INSPECT sees.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INSPECTREP.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TEXT             PIC X(20)    VALUE SPACES.
       01  WS-WORK             PIC X(20)    VALUE SPACES.
       01  WS-ALL-A            PIC 9(3)     VALUE ZERO.
       01  WS-LEAD-SP          PIC 9(3)     VALUE ZERO.
       01  WS-SHARED           PIC 9(3)     VALUE ZERO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-TEXT
           MOVE WS-TEXT TO WS-WORK
           INSPECT WS-TEXT TALLYING WS-ALL-A FOR ALL "A"
           INSPECT WS-TEXT TALLYING WS-LEAD-SP FOR LEADING SPACE
           INSPECT WS-TEXT TALLYING WS-SHARED FOR ALL "A"
           INSPECT WS-TEXT TALLYING WS-SHARED FOR ALL "B"
           INSPECT WS-WORK REPLACING ALL "A" BY "@"
           INSPECT WS-WORK REPLACING LEADING SPACE BY "."
           DISPLAY "ALLA   " WS-ALL-A
           DISPLAY "LEADSP " WS-LEAD-SP
           DISPLAY "SHARED " WS-SHARED
           DISPLAY "WORK  [" WS-WORK "]"
           STOP RUN.
