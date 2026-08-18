testprob02 -- three different tallies of the same physical quantity.
1     1  -2.45    -1    pd5=.3  $ boron ball with volume source
2     2  -2.7   1 -2 4  pd5=1   $ aluminum shell
3     2  -2.7   2 -3 4  pd5=1   $ aluminum shell
4     0         3       pd5=1   $ outside world
5     2  -2.7   5 -4    pd5=1   $ al. ball to av. dxtran/tally2 con.
6     2  -2.7     -5    pd5=1   $ little aluminum ball for tally 4
 
1     so  5
2     so  7
3     so 10
4     sy  7   1.95
5     sy  7    .3
 
c    volume source in boron ball, biased in position.
c    the symmetry is sufficient for the bias to be a fair game.
sdef  cel d4   x d1   y d2   z d3   erg=1 
si1   -5 5
sp1    0 1
sc2  position is biased toward the dxtran and the ring detector.
si2   a -5 5
sp2   1 1
sb2   1 2
si3   -5 5
sp3    0 1
si4 l 1
sp4 v 
c
m1     5010.00 .196 5011.40c .804 nlib=03d  $ natural boron
m2    13027.40c 1   $ aluminum-27
m3     5010.0 .250 5011.40c .750 nlib .03d  $ enriched b-10 of .250
pert1:n  cell=1  mat=3
ctme 60
phys:n  1.2     $ cross sections above 1.2 mev will be expunged.
c
c    all tallies have the same energy bins.
e0    .01 .03 .1 .3 1
fc2  average flux on surface 2.
f2:n  2
f1:n 1
c1   -.8 3i 0 4i 1 t
fq1  c e
tf1  1 7r
ft2  tmc -2 .05
t2   -2 9i 3 10 100
fq2  t e
ft1  frv 3 4 5   geb 1 2 0
fc4  average flux in cell 6.
f4:n  6
dd5  .003
fq5  u e
fu5  1 8i 10
ft5  inc
fc5  average flux at ring detector.
fy5:n 5 4.89 .7
dxc:n  1 .7 .9 0 1 1
dd1  .04 100
thtme -10 0 .5 1 2
#    tmp1  tmp2  tmp3  tmp4  tmp5
  1  1e-8  2e-8  3e-8  4e-8  5e-8
  2  2e-8  3e-8  5e-8  4e-8  3e-8
  3  1e-8  5e-8  4e-8  3e-8  2e-8
  4     0     0     0     0     0
  5  2e-8  1e-8  5e-8  3e-8  1e-8
  6  3e-8  2e-8  1e-8  2e-8  1e-8
c
dxt:n 0 7 0 1 1.9  $ dxtran around cell 6, inside cell 5.
imp:n 1 1 1 0 1 1
c
nps   5000         $ run 5000 histories.
print 10 72 170
prdmp 2500 625 -1 2       $ print mctal file.
c    For backward compatability, set the first calculation of the
c  point detector average contribution at nps =  200
dbcn 14j 1 51j 200
ptrac buffer=2 file=asc event=src nps=1,200 cell=3
