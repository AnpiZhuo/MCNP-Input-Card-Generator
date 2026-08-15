Test of unc - uncollided secondaries card
10  1 -18.7  -1                 
20  0  1 -9                
30  0  9 -10               

1  rpp   -1 1  -1 1 0 1 
9  so 1000
10  so 2000

mode p
imp:p 1 1 0
unc:p 0 0 0 
sdef pos= 0 0 -.001 vec= 0 0 1 dir=1 erg=20 par=p ara=1.0
m1 74000 1.0
nps 1e5
f5:p  50 0 100 1.0 $ uncollided should be zero
fmesh14:p geom=xyz out=jk  inc= 1 2
       origin= 49.0 -10.0 90.0  
       imesh 51  iints 1
       jmesh 10 jints 2 
       kmesh 110.0 kints 2
prdmp 999999 999999 -1 999999 8000
print
c    For backward compatability, set the first calculation of the
c  point detector average contribution at nps =  200
dbcn 66j 200

