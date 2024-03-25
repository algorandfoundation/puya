# Python builtins

## len -> .length

why? len() is typed as returning int, CPython checks that it returns _exactly_ int

could've made a ulen but at that point easier to just add .length which returns UInt64 
and avoid import

## range -> urange

## enumerate -> uenumerate

## reversed
