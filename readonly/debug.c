// config global
// FGVM01TM23003837 (global) (Interim)# config system console
// FGVM01TM23003837 (console) (Interim)# set output standard
// FGVM01TM23003837 (console) (Interim)# end

// !
sha-pai-fpx-01 # diagnose debug reset
// diagnose sys scanunit debug all
// dia ips debug enable all
sha-pai-fpx-01 # diagnose wad debug enable all
sha-pai-fpx-01 # diag wad debug ips-filter
dia ips debug enable all
sha-pai-fpx-01 # diagnose debug enable
// FGVM01TM24003952 (Interim)# diagnose test application wad 1000

