// end
config global
diag debug enable
diag test app wad 2200
diag test app wad 328
// expect -e "Toggle vf cache check from ON to OFF" -for TOGGLE_VF_CACHE -t 10
diag test app wad 329
// expect -e "Toggle vf ftgd query from ON to OFF" -for TOGGLE_VF_FGD -t 10
diag test app wad 330
// expect -e "Toggle vf api check from ON to OFF" -for TOGGLE_VF_API -t 10
