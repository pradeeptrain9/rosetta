      *> Storage usage changes the arithmetic, not just the byte layout.
      *> Gotcha 1: moving a 9-digit value into PIC 9(4) COMP keeps the
      *>           low-order FOUR DECIMAL digits, because GnuCOBOL truncates
      *>           to the picture rather than to the binary word.
      *> Gotcha 2: FUNCTION LENGTH of a COMP item is its STORAGE SIZE in
      *>           bytes, not its digit count. For DISPLAY usage the two
      *>           happen to coincide, which hides the bug.
      *> Gotcha 3: COMP-3 packs two digits per byte plus a sign nibble, so
      *>           its length is not its digit count either.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. COMPFIELD.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-IN               PIC 9(9)     VALUE ZERO.
       01  WS-BIN              PIC 9(4) USAGE COMP        VALUE ZERO.
       01  WS-BIN-SIGNED       PIC S9(4) USAGE COMP       VALUE ZERO.
       01  WS-PACKED           PIC S9(7)V99 USAGE COMP-3  VALUE ZERO.
       01  WS-DISP             PIC 9(9)     VALUE ZERO.
       01  WS-PACK-OUT         PIC Z(6)9.99.
       01  WS-LEN-BIN          PIC 9(2)     VALUE ZERO.
       01  WS-LEN-PACK         PIC 9(2)     VALUE ZERO.
       01  WS-LEN-DISP         PIC 9(2)     VALUE ZERO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-IN
           MOVE WS-IN TO WS-BIN
           MOVE WS-IN TO WS-PACKED
           COMPUTE WS-BIN-SIGNED = 0 - WS-BIN
           MOVE WS-BIN TO WS-DISP
           MOVE WS-PACKED TO WS-PACK-OUT
           COMPUTE WS-LEN-BIN  = FUNCTION LENGTH(WS-BIN)
           COMPUTE WS-LEN-PACK = FUNCTION LENGTH(WS-PACKED)
           COMPUTE WS-LEN-DISP = FUNCTION LENGTH(WS-IN)
           DISPLAY "IN       " WS-IN
           DISPLAY "BIN      " WS-BIN
           DISPLAY "BINSIGN  " WS-BIN-SIGNED
           DISPLAY "DISP     " WS-DISP
           DISPLAY "PACKED  [" WS-PACK-OUT "]"
           DISPLAY "LENBIN   " WS-LEN-BIN
           DISPLAY "LENPACK  " WS-LEN-PACK
           DISPLAY "LENDISP  " WS-LEN-DISP
           STOP RUN.
