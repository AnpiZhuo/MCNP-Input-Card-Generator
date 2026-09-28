# C810 语义锚点表（SDEF / 分布家族）

> **本文件由 tools/c810_extract.py 从 C810.pdf 生成，勿手改。**
>
> 权威手册：`D:\MCNP\MCNP6\C810.pdf`（PDF 页 − 525 = 印刷页 3-x，页码由脚本逐页核对）。
> 原文由 `tools/c810_extract.py` 按「锚点 id → (PDF 页, 起始正则, 结束正则, 关键短语)」
> 表**脚本抽取**（不手抄）；原文里的连字（`ﬁ`）、软连字符、`−`(U+2212) 等排版字符
> 会被归一成 ASCII，实词逐字未改。
>
> 机检：`tests/unit/test_c810_anchors.py` 断言每个锚点在原文里**确实包含**其关键短语，
> 且 `app/generator/source_spec.py` 引用的每个 `#C810-…` id 都在本表里。


## #C810-3-4-COMMENTS

来源：C810.pdf PDF p529 = 印刷 3-4

原文：

```text
Comment cards can be used anywhere in the INP file after the problem title card and before the last
blank terminator card. These cards must have a C anywhere in columns 1-5 followed by at least
one blank. Comment cards are printed only with the input file listing and not anywhere else in the
MCNP output file. The FCn input card is available for user comments and is printed as a heading
for tally n (as a tally title, for example). The SCn card is available for user comments and is printed
as a heading for source probability distribution n.
```

关键短语：

- `Comment cards can be used anywhere in the INP`

- `after the problem title card and before the last blank terminator card`

- `must have a C anywhere in columns 1-5 followed by at least one blank`

- `Comment cards are printed only with the input file listing`


## #C810-3-4-CONTINUATION

来源：C810.pdf PDF p529 = 印刷 3-4

原文：

```text
Blanks in the
first five columns indicate a continuation of the data from the last named card. Alternatively, an &
(ampersand) preceded by at least one blank ending a line indicates data will continue on the
following card. Data on this continuation card can be in columns 1-80. Completely blank cards are
reserved as delimiters between major sections of the input file. An individual entry must be entirely
on one line. There can be only one card of any given type for a given particle designation (see page
3-7). Integers must be entered where integer input is required. Other numerical data can be entered
as integer or floating point and will be read properly by MCNP. (In fact, noninteger numerical data
can be entered in any form acceptable to a Fortran E-edit descriptor.)
```

关键短语：

- `Blanks in the first five columns indicate a continuation of the data from the last named card`

- `Data on this continuation card can be in columns 1-80`

- `Completely blank cards are`


## #C810-3-30-TR-CARD

来源：C810.pdf PDF p555 = 印刷 3-30

原文：

```text
5. TRn Coordinate Transformation Card
Form: TRn O1 O2 O3 B1 B2 B3 B4 B5 B6 B7 B8 B9 M
n = number of the transformation: 1 ≤ n ≤ 999. ∗TRn means that
the Bi are angles in degrees rather than being the cosines of the
angles.
O1 O2 O3 = displacement vector of the transformation.
B1 to B9 = rotation matrix of the transformation.
M = 1 (the default) means that the displacement vector is the location
of the origin of the auxiliary coordinate system, defined in the
main system.
= -1 means that the displacement vector is the location of the
origin of the main coordinate system, defined in the auxiliary
system.
Default: TRn 0 0 0 1 0 0 0 1 0 0 0 1 1
```

关键短语：

- `Form: TRn O1 O2 O3 B1 B2 B3 B4 B5 B6 B7 B8 B9 M`

- `M = 1 (the default) means that the displacement vector is the location of the origin of the auxiliary coordinate system, defined in the main system`

- `= -1 means that the displacement vector is the location of the origin of the main coordinate system, defined in the auxiliary system`

- `Default: TRn 0 0 0 1 0 0 0 1 0 0 0 1 1`


## #C810-3-31-TR-B-MATRIX

来源：C810.pdf PDF p556 = 印刷 3-31

原文：

```text
The B matrix specifies the relationship between the directions of the axes of the two coordinate
systems. Bi is the cosine of the angle (or the angle itself, in degrees in the range from 0 to 180, if
the optional asterisk is used) between an axis of the main coordinate system (x,y,z) and an axis of
the auxiliary coordinate system x′y′z′ as follows:
Element B1 B2 B3 B4 B5 B6 B7 B8 B9
Axes x,x' y,x' z,x' x,y' y,y' z,y' x,z' y,z' z,z'
The meanings of the Bi do not depend on M. It is usually not necessary to enter all of the elements
of the B matrix. These patterns are acceptable:
1. All nine elements.
2. Two of the three vectors either way in the matrix (6 values). MCNP will create the third
vector by cross product.
3. One vector each way in the matrix (5 values). The component in common must be less
than 1. MCNP will fill out the matrix by the Eulerian angles scheme.
4. One vector (3 values). MCNP will create the other two vectors in some arbitrary way.
5. None. MCNP will create the identity matrix.
A vector consists of the three elements in either a row or a column in the matrix. In all cases, MCNP
cleans up any small nonorthogonality and normalizes the matrix. In this process, exact vectors like
(1,0,0) are left unchanged. A warning message is issued if the nonorthogonality is more than about
0.001 radian.
Pattern #5 is appropriate when the transformation is a pure translation. Pattern #4 is appropriate
when the auxiliary coordinate system is being used to describe a set of surfaces that are all surfaces
of rotation about a common skew axis. Patterns 2 and 3 are about equally useful in more general
cases. Pattern #1 is required if one of the systems is right-handed and the other is left-handed.
```

关键短语：

- `Element B1 B2 B3 B4 B5 B6 B7 B8 B9`

- `Axes x,x' y,x' z,x' x,y' y,y' z,y' x,z' y,z' z,z'`

- `The meanings of the Bi do not depend on M`

- `2. Two of the three vectors either way in the matrix (6 values). MCNP will create the third vector by cross product`

- `3. One vector each way in the matrix (5 values). The component in common must be less than 1. MCNP will fill out the matrix by the Eulerian angles scheme`

- `4. One vector (3 values). MCNP will create the other two vectors in some arbitrary way`

- `5. None. MCNP will create the identity matrix`


## #C810-3-56-PAR

来源：C810.pdf PDF p581 = 印刷 3-56

原文：

```text
The specification of WGT, EFF and PAR must be only an explicit value. A distribution is not
allowed. The allowed value for PAR is 1 or N for neutron, 2 or P for photon, or 3 or E for electron.
The default is the lowest of these three that corresponds to an actual or default entry on the MODE
card. Only one kind of particle is allowed in an SDEF source. A special syntax allows PAR to be
specified as 4 or F to make the source type a positron rather than an electron in a MODE E or P E
or N P E problem.
```

关键短语：

- `The specification of WGT, EFF and PAR must be only an explicit value`

- `A distribution is not allowed`

- `The allowed value for PAR is 1 or N for neutron, 2 or P for photon, or 3 or E for electron`

- `The default is the lowest of these three that corresponds to an actual or default entry on the MODE card`

- `Only one kind of particle is allowed in an SDEF source`

- `A special syntax allows PAR to be specified as 4 or F to make the source type a positron rather than an electron in a MODE E or P E or N P E problem`


## #C810-3-60-CEL-PATH

来源：C810.pdf PDF p585-586 = 印刷 3-60 ~ 3-61

原文：

```text
Source cell path for repeated structures or lattices
The only part of the MCNP source specification that is different when the source is in a repeated
structure part of the geometry is the use of the CEL parameter on the SDEF card. CEL must have
a value that is a path, enclosed in parentheses, from level n to level 0, where level n is not
necessarily the bottom:
( cn < cn - 1 < .... < c0 )
ci is a cell in the universe that fills cell ci-1, or is zero, or is Dm for a distribution of cells in the
repeated structure case. Dm is not valid for a lattice. ci can have a minus sign and is discussed more
below. Dm cannot have a minus sign. If ci = 0, the cell at that level is searched for. Recall that level
n is not necessarily the bottom level in the problem. If ci is one specific element in a lattice, it is
indicated as: ... < ci [j1 j2 j3]< ...
The coordinate system for position and direction sampling (pds) is the coordinate system of the first
negative or zero ci in the source path starting from the right and proceeding left. Each entry in the
source path represents a geometry level, where level zero is the last source path entry, level one the
second to the left, etc., and level zero is above level one, level two is below level one. The pds level
is the level associated with the pds cell or pds coordinate system. All levels above the pds level must
be included in the source path. Levels below the pds level need not be specified, and when given,
may include one or more zero entries. The default pds level is the first entry in the source path when
the path has no negative or zero entry.
Position rejection is done in cells at all levels where ci ≠ 0, but if any ci has a negative universe
number on its cell card and is at or above the pds level, higher level cells are not checked.
The following chart illustrates the idea of the pds level.
CEL Source Path Cell of pds Level pds Level
(5<6<7<8) 5 3
(6<-7<8) 7 1
(0<4<0<-6<7<8) 6 2
(0<6[0 0 0]<-7[1 0 0]<8) 7 1
(0<6[0 0 0]<7[1 0 0]<8) Will be determined 3

Lattice cell elements that are defined using the expanded FILL card (see page 3-29) can be
uniformly sampled automatically. This feature is applied to lattice cell entries in the source path
that lack an explicit lattice index AND that are at or above the pds level. Lattice cells not defined
by the expanded FILL card must include an explicit lattice index when at or above the pds level.
Rejection of automatically sampled lattice elements depends on the entry before the lattice cell
number in the source path.
Assume the following cell cards:
7 0 surfaces lat=1 u=1 fill=0:2 0:0 0:0 1 2 3
cells 8 and 9 belong to universe 2
cells 10 and 11 belong to universe 3
Cell 7 is a lattice with three existing elements: [0 0 0] is filled by itself [u=1], [1 0 0] is filled by
cells 8 and 9 [u=2], and [2 0 0] is filled by cells 10 and 11 [u=3]. The following combinations show
which elements are accepted and which are rejected.
CEL Source Path Accepted Rejected
7 All elements None
(0<7) All elements None
(8<7) [1 0 0] [0 0 0], [2 0 0]
(10<7) [2 0 0] [0 0 0], [1 0 0]
The sampling efficiency for cell 7 in the OUTP file will reflect the element rejections. Lattice cell
entries that lack an explicit lattice index AND are below the pds level are not sampled. Instead, the
appropriate lattice element is determined by the input source position.
Lattice element sampling is independent from position sampling. First a lattice element is chosen,
then a position is chosen. If the sampled position is not in the sampled lattice element, the position
is resampled until it is in the specified source path and in the lattice element chosen or until an
efficiency error occurs. The lattice elements will not be resampled to accommodate the sampled
position. Lattice element rejection is done only as described above.
Using the previous description of lattice cell 7, add that cell 6 is filled by cell 7. The source path
becomes (0<7<6). Three elements of the lattice exist [fill=0:2 0:0 0:0] but element [0 0 0] now is
cut off by cell 6. Lattice element [0 0 0] still will be sampled one-third of the time. The first time
element [0 0 0] is sampled a FATAL error will occur because the sampled position, no matter what
it is, will be rejected because element [0 0 0] does not exist. CAUTION: Implement automatic
lattice sampling carefully and ensure that all of the lattice elements specified on the expanded FILL
card really do exist.
See Chapter 4 page 4-27 for a detailed example of specifying a source in a lattice geometry.
```

关键短语：

- `CEL must have a value that is a path, enclosed in parentheses, from level n to level 0`

- `where level n is not necessarily the bottom`

- `Each entry in the source path represents a geometry level`

- `ci is a cell in the universe that fills cell ci-1, or is zero, or is Dm for a distribution of cells in the repeated structure case`

- `If ci is one specific element in a lattice, it is indicated as`

- `The coordinate system for position and direction sampling (pds) is the coordinate system of the first negative or zero ci in the source path`

- `CEL Source Path Cell of pds Level pds Level`

- `Lattice cell elements that are defined using the expanded FILL card`


## #C810-3-55-VAR-FORMS

来源：C810.pdf PDF p580 = 印刷 3-55

原文：

```text
The equal signs are optional. The source variables are not quite the same as MCNP variables that
the source must set. Many are intermediate quantities that control the sampling of the final
variables. All have default values. The specification of a source variable has one of these three
forms:
1. explicit value,
2. a distribution number prefixed by a D, or
3. the name of another variable prefixed by an F, followed by a distribution number
prefixed by a D. Var = Dn means that the value of source variable var is sampled from
distribution n. Var Fvar′ Dn means that var is sampled from distribution n that depends
on the variable var′. Only one level of dependence is allowed. Each distribution may be
used for only one source variable.
```

关键短语：

- `The specification of a source variable has one of these three forms`

- `explicit value`

- `a distribution number prefixed by a D`

- `the name of another variable prefixed by an F, followed by a distribution number`

- `Var = Dn means that the value of source variable var is sampled from distribution n`

- `Var Fvar′ Dn means that var is sampled from distribution n that depends on the variable var′`


## #C810-3-55-SAMPLING-ORDER

来源：C810.pdf PDF p580 = 印刷 3-55

原文：

```text
MCNP samples the source variables in an order set up according to the needs of the particular
problem. Each dependent variable must be sampled after the variable it depends on has been
sampled. If the value of one variable influences the default value of another variable or the way it
is sampled, as SUR influences DIR, they may have to be sampled in the right order. The scheme
used in MCNP to set up the order of sampling is complicated and may not always work. If it fails,
```

关键短语：

- `MCNP samples the source variables in an order set up according to the needs of the particular problem`

- `Each dependent variable must be sampled after the variable it depends on has been sampled`


## #C810-3-55-ONE-LEVEL

来源：C810.pdf PDF p580 = 印刷 3-55

原文：

```text
Only one level of dependence is allowed. Each distribution may be
used for only one source variable.
```

关键短语：

- `Only one level of dependence is allowed`

- `Each distribution may be used for only one source variable`


## #C810-3-56-TABLE-3-3

来源：C810.pdf PDF p580-581 = 印刷 3-55 ~ 3-56

原文：

```text
Table 3.3: Source Variables
Variable Meaning Default
CEL Cell Determined from XXX, YYY, ZZZ and
possibly UUU, VVV, WWW
SUR Surface Zero (means cell source)
ERG Energy (MeV) 14 MeV
TME Time (shakes) 0

Table 3.3: Source Variables
Variable Meaning Default
DIR µ, the cosine of the angle between VEC Volume case: µ is sampled uniformly in
and UUU, VVV, WWW (Azimuthal -1 to 1 (isotropic)
angle is always sampled uniformly in 0o Surface case: p(µ) = 2µ in 0 to 1
to 360o) (cosine distribution)
VEC Reference vector for DIR Volume case: required unless isotropic
Surface case: vector normal to the
surface with sign determined by NRM
NRM Sign of the surface normal + 1
POS Reference point for position sampling 0,0,0
RAD Radial distance of the position from 0
POS or AXS
EXT Cell case: distance from POS along 0
AXS
Surface case: Cosine of angle from
AXS
AXS Reference vector for EXT and RAD No direction
X x-coordinate of position No X
Y y-coordinate of position No Y
Z z-coordinate of position No Z
CCC Cookie-cutter cell No cookie-cutter cell
ARA Area of surface (required only for direct None
contributions to point detectors from
plane surface source.)
WGT Particle weight 1
EFF Rejection efficiency criterion for .01
position sampling
PAR Particle type source will emit 1=neutron if MODE N or N P or N P E
2=photon if MODE P or P E
3=electron if MODE E
TR Source particle transformation TR=n or None
distribution of transformations TR=Dn
```

关键短语：

- `Table 3.3: Source Variables`

- `Determined from XXX, YYY, ZZZ`

- `Zero (means cell source)`

- `Energy (MeV)`

- `14 MeV`

- `Time (shakes)`

- `Reference vector for DIR`

- `Sign of the surface normal`

- `Radial distance of the position from`

- `POS or AXS`

- `Cell case: distance from POS along`

- `Reference vector for EXT and RAD`

- `Particle weight`

- `Rejection efficiency criterion for`

- `position sampling`

- `.01`

- `Particle type source will emit`

- `distribution of transformations TR=Dn`


## #C810-3-63-SI-OPTIONS

来源：C810.pdf PDF p587-588 = 印刷 3-62 ~ 3-63

原文：

```text
SIn Source Information Card
3. SPn Source Probability Card
4. SBn Source Bias Card
Form: SIn option I1 ... Ik
n = distribution number (n = 1,999)
option = how the Ii's are to be interpreted. Allowed values are:
omitted or H-bin boundaries for a histogram distribution,
for scalar variables only. This is the default.

L-discrete source variable values
A-points where a probability density distribution is defined
S-distribution numbers
I1 ... Ik = source variable values or distribution numbers
Default: SIn HIi ... Ik
```

关键短语：

- `Source Information Card`

- `distribution number (n = 1,999)`

- `how the Ii's are to be interpreted. Allowed values are`

- `omitted or H-bin boundaries for a histogram distribution`

- `L-discrete source variable values`

- `A-points where a probability density distribution is defined`

- `S-distribution numbers`

- `source variable values or distribution numbers`


## #C810-3-63-SP-OPTIONS

来源：C810.pdf PDF p587-589 = 印刷 3-62 ~ 3-64

原文：

```text
SPn Source Probability Card
4. SBn Source Bias Card
Form: SIn option I1 ... Ik
n = distribution number (n = 1,999)
option = how the Ii's are to be interpreted. Allowed values are:
omitted or H-bin boundaries for a histogram distribution,
for scalar variables only. This is the default.

L-discrete source variable values
A-points where a probability density distribution is defined
S-distribution numbers
I1 ... Ik = source variable values or distribution numbers
Default: SIn HIi ... Ik
Form: SPn option P1 ... Pk
or: SPn f a b
n = distribution number (n = 1,999)
option = how the Pi are to be interpreted. Allowed values are:
omitted-same as D for an H or L distribution. Probability
density for an A distribution on SI card.
D-bin probabilities for an H or L distribution on SI card.
This is the default.
C-cumulative bin probabilities for an H or L distribution
on SI card.
V-for cell distributions only. Probability is proportional
to cell volume (times Pi if the Pi are present).
Pi ... Pk = source variable probabilities
f = designator (negative number) for a built-in function
a b = parameters for the built-in function (see Table 3.4)
Default: SPn D P1 ...Pk
Form: SBn option B1 ... Bk
or: SBn f a b
n, option, f, a, and b are the same as for the SPn card, except that the
only values allowed for f are -21 and -31
Bi ... Bk = source variable biased probabilities
Default: SBn D B1 ... Bk
```

关键短语：

- `Source Probability Card`

- `or: SPn f a b`

- `how the Pi are to be interpreted. Allowed values are`

- `omitted-same as D for an H or L distribution`

- `density for an A distribution on SI card`

- `D-bin probabilities for an H or L distribution on SI card`

- `This is the default.`

- `C-cumulative bin probabilities for an H or L distribution`

- `V-for cell distributions only. Probability is proportional to cell volume`

- `designator (negative number) for a built-in function`


## #C810-3-63-H-FIRST-ZERO

来源：C810.pdf PDF p588-589 = 印刷 3-63 ~ 3-64

原文：

```text
The first form of the SP card, where the first entry is positive or nonnumeric, indicates that it and
its SI card define a probability distribution function. The entries on the SI card are either values of
the source variable or, when the S option is used, distribution numbers. The entries on the SP card
are probabilities that correspond to the entries on the SI card.
When the H option is used, the numerical entries on the SI card are bin boundaries and must be
monotonically increasing. The first numerical entry on the SP card must be zero and the following
entries are bin probabilities or cumulative bin probabilities, depending on whether the D or C
option is used. The probabilities need not be normalized. The variable is sampled by first sampling
a bin according to the bin probabilities and then sampling uniformly within the chosen bin.
When the A option is used, the entries on the SI card are values of the source variable at which the
probability density is defined. The entries must be monotonically increasing, and the lowest and
highest values define the range of the variable. The numerical entries on the SP card are values of

the probability density corresponding to the values of the variable on the SI card. They need not be
normalized. In the sampling process, the probability density is linearly interpolated between the
specified values. The first and last entries on the SP card will typically be zero, but nonzero values
are also allowed.
When the L option is used, the numerical entries on the SI card are discrete values of the source
variable, such as cell numbers or the energies of photon spectrum lines. The entries on the SP card
are either probabilities of those discrete values or cumulative probabilities, depending on whether
the D or C option is used. The entries on the SI card need not be monotonically increasing.
```

关键短语：

- `The first form of the SP card, where the first entry is positive or nonnumeric`

- `the numerical entries on the SI card are bin boundaries and must be monotonically increasing`

- `The first numerical entry on the SP card must be zero`

- `the following entries are bin probabilities or cumulative bin probabilities`

- `The probabilities need not be normalized`

- `When the A option is used, the entries on the SI card are values of the source variable`

- `The numerical entries on the SP card are values of the probability density corresponding`

- `the probability density is linearly interpolated between the specified values`

- `When the L option is used, the numerical entries on the SI card are discrete values`


## #C810-3-64-BUILTIN-FORM

来源：C810.pdf PDF p588-589 = 印刷 3-63 ~ 3-64

原文：

```text
The second form of the SP card, where the first entry is negative, indicates that a built-in analytic
function is to be used to generate a continuous probability density function for the source variable.
```

关键短语：

- `The second form of the SP card, where the first entry is negative`

- `indicates that a built-in analytic function is to be used to generate a continuous probability density function`


## #C810-3-64-SB-RULES

来源：C810.pdf PDF p588-589 = 印刷 3-63 ~ 3-64

原文：

```text
The SB card is used to provide a probability distribution for sampling that is different from the true
probability distribution on the SP card. Its purpose is to bias the sampling of its source variable to
improve the convergence rate of the problem. The weight of each source particle is adjusted to
compensate for the bias. All rules that apply to the first form of the SP card apply to the SB card.
```

关键短语：

- `The weight of each source particle is adjusted to compensate for the bias`

- `All rules that apply to the first form of the SP card apply to the SB card`


## #C810-3-64-SI-S

来源：C810.pdf PDF p588-589 = 印刷 3-63 ~ 3-64

原文：

```text
The S option allows sampling among distributions, one of which is chosen for further sampling.
This feature makes it unnecessary to fold distributions together and is essential if some of the
distributions are discrete and others are linearly interpolated. The distributions listed on an SI card
with the S option can themselves also have the S option. MCNP can handle this structure to a depth
of about 20, which should be far more than necessary for any practical problem. Each distribution
number on the SI card can be prefixed with a D, or the D can be omitted. If a distribution number
is zero, the default value for the variable is used. A distribution can appear in more than one place
with an S option, but a distribution cannot be used for more than one source variable.
```

关键短语：

- `The S option allows sampling among distributions, one of which is chosen for further sampling`

- `Each distribution number on the SI card can be prefixed with a D, or the D can be omitted`

- `If a distribution number is zero, the default value for the variable is used`

- `a distribution cannot be used for more than one source variable`


## #C810-3-64-SP-V

来源：C810.pdf PDF p588-589 = 印刷 3-63 ~ 3-64

原文：

```text
The V option on the SP card is a special case used only when the source variable is CEL. This
option is useful when the cell volume is a factor in the probability of particle emission. If MCNP
cannot calculate the volume of such a cell and the volume is not given on a VOL card, you have a
FATAL error.
```

关键短语：

- `The V option on the SP card is a special case used only when the source variable is CEL`

- `when the cell volume is a factor in the probability of particle emission`

- `you have a FATAL error`


## #C810-3-65-TABLE-3-4

来源：C810.pdf PDF p590-591 = 印刷 3-65 ~ 3-66

原文：

```text
Table 3.4: Built-In Functions for Source Probability and Bias Specification
Function No. and
Source Variable Input Parameters Description
ERG -2 a Maxwell fission spectrum
ERG -3 a b Watt fission spectrum
ERG -4 a b Gaussian fusion spectrum
ERG -5 a Evaporation spectrum
ERG -6 a b Muir velocity Gaussian fusion spectrum
ERG -7 a b Spare
DIR, RAD, or EXT -21 a Power law p(x) = c|x|a
DIR or EXT -31 a Exponential: p(µ) = ceaµ
TME, X, Y, or Z -41 a b Gaussian distribution of time t or
position coordinates x,y,z.
f = -2 Maxwell fission energy spectrum: p(E) = C E1/2 exp(-E/a), where a is a temperature in
MeV.
Default: a = 1.2895 MeV
f = -3 Watt fission energy spectrum: p(E) = C exp(-E/a) sinh(bE)1/2.
Defaults: a = 0.965 MeV, b = 2.29 MeV-1.
See Appendix H page H-3 for additional parameters appropriate to neutron-induced fission in
various materials and for spontaneous fission.
f = -4 Gaussian fusion energy spectrum: p(E) = C exp[-((E-b)/a)2], where a is the width in MeV
and b is the average energy in MeV. Width here is defined as the ∆E above b where the value of the
exponential is equal to e-1. If a < 0, it is interpreted as a temperature in MeV and b must also be
negative. If b = -1, the D-T fusion energy is calculated and used for b. If b = -2, the D-D fusion
energy is calculated and used for b. Note that a is not the "full-width-at-half-maximum," but is
related to it by FWHM = a (ln 2)1/2.
Defaults: a = -0.01 MeV, b = -1 (DT fusion at 10 keV).
f = -5 Evaporation energy spectrum: p(E) = C E exp(-E/a).
Default: a = 1.2895 MeV.
f = -6 Muir velocity Gaussian fusion energy spectrum: p(E) = C exp - ((E1/2 - b1/2)/a)2,
where a is the width in MeV1/2, and b is the energy in MeV corresponding to the average speed.
Width here is defined as the change in velocity above the average velocity b1/2, where the value of
the exponential is equal to e-1. To get a spectrum somewhat comparable to f = -4, the width can be
determined by a = (b + a4)1/2 -b1/2, where a4 is the width used with the Gaussian fusion energy
spectrum. If a < 0, it is interpreted as a temperature in MeV. If b = -1, the D-T fusion energy is
calculated and used for b. If b = -2, the D-D fusion energy is calculated and used for b.
Defaults: a = -0.01 MeV, b = -1 (DT fusion at 10 keV).
f = -7 Spare energy spectrum. The basic framework for another energy spectrum is in place to
make it easier for a user to add a spectrum of his own. The subroutines to change are SPROB,
SPEC, SMPSRC, and possibly CALCPS.

f = -21 Power law: p(x) = c|x|a.
The default depends on the variable. For DIR, a = 1. For RAD, a = 2, unless AXS is defined or JSU
≠ 0, in which case a = 1. For EXT, a = 0.
f = -31 Exponential: p(µ) = ceaµ.
Default: a = 0.
f = -41 Gaussian distribution of time t or position coordinates x,y,z: p(t)=c exp[-(1.6651092(t-b)/
a)2], where a is the width at half maximum and b is the mean; for time, a and b are in shakes, while,
for position variables, the units are centimeters. Note: this distribution may be written in normal
form as p(t)=c exp[-(t-b)2/2σ2]. The FWHM is thus a=(8 ln 2)1/2 σ .
```

关键短语：

- `Table 3.4: Built-In Functions for Source Probability and Bias Specification`

- `Maxwell fission energy spectrum`

- `Watt fission energy spectrum`

- `Gaussian fusion energy spectrum`

- `Evaporation energy spectrum`

- `Muir velocity Gaussian fusion energy spectrum`

- `Spare energy spectrum`

- `Power law p(x) = c|x|a`

- `Exponential: p(µ) = ceaµ`

- `Gaussian distribution of time t or`

- `Default: a = 1.2895 MeV`

- `a = 0.965 MeV, b = 2.29 MeV`

- `a = -0.01 MeV, b = -1 (DT fusion at 10 keV)`

- `For DIR, a = 1`

- `For RAD, a = 2, unless AXS is defined or JSU`

- `For EXT, a = 0`

- `f = -31 Exponential`

- `Default: a = 0.`


## #C810-3-66-BUILTIN-VARS

来源：C810.pdf PDF p591 = 印刷 3-66

原文：

```text
The built-in functions can be used only for the variables shown in Table 3.3. Any of the built-in
functions can be used on SP cards, but only -21 and -31 can be used on SB cards. If a function is
used on an SB card, only that same function can be used on the corresponding SP card. The
combination of a regular table on the SI and SP cards with a function on the SB card is not allowed.
```

关键短语：

- `The built-in functions can be used only for the variables shown in Table 3.3`

- `only -21 and -31 can be used on SB cards`

- `only that same function can be used on the corresponding SP card`

- `The combination of a regular table on the SI and SP cards with a function on the SB card is not allowed`


## #C810-3-66-TRUNC-WEIGHT

来源：C810.pdf PDF p591 = 印刷 3-66

原文：

```text
A built-in function on an SP card can be biased or truncated or both by a table on SI and SB cards.
The biasing affects only the probabilities of the bins, not the shape of the function within each bin.
If it is biased, the function is approximated within each bin by n equally probable groups such that
the product of n and the number of bins is as large as possible but not over 300. Unless the function
is -21 or -31, the weight of the source particle is adjusted to compensate for truncation of the
function by the entries on the SI card.
```

关键短语：

- `The biasing affects only the probabilities of the bins, not the shape of the function within each bin`

- `the product of n and the number of bins is as large as possible but not over 300`

- `Unless the function is -21 or -31, the weight of the source particle is adjusted to compensate for truncation of the function by the entries on the SI card`


## #C810-3-66-SPECIAL-DEFAULTS

来源：C810.pdf PDF p591 = 印刷 3-66

原文：

```text
Special defaults are available for distributions that use built-in functions.
1. If SB f is present and SP f is not, an SP f with default input parameters is, in effect,
provided by MCNP.
2. If only an SI card is present for RAD or EXT, an SP -21 with default input parameters
is, in effect, provided.
3. If only SP -21 or SP -31 is present for DIR or EXT, an SI 0 1, for -21, or SI -1 1, for
-31, is, in effect, provided.
4. If SI x and SP -21 are present for RAD, the SI is treated as if it were SI 0 x.
5. If SI x and SP -21 or SP -31 are present for EXT, the SI is treated as if it were SI -x x.
```

关键短语：

- `Special defaults are available for distributions that use built-in functions`

- `If SB f is present and SP f is not, an SP f with default input parameters`

- `If only an SI card is present for RAD or EXT, an SP -21 with default input parameters`

- `If only SP -21 or SP -31 is present for DIR or EXT, an SI 0 1, for -21, or SI -1 1`

- `If SI x and SP -21 are present for RAD, the SI is treated as if it were SI 0 x`

- `If SI x and SP -21 or SP -31 are present for EXT, the SI is treated as if it were SI -x x`


## #C810-3-66-DS-CARD

来源：C810.pdf PDF p591-592 = 印刷 3-66 ~ 3-67

原文：

```text
Dependent Source Distribution Card
Form: DSn option J1 ... Jk
or: DSn T I1 J1 ... Ik Jk
or: DSn Q V1 S1 ... Vk Sk
n = distribution number (n = 1,999)
option = how the Ji are to be interpreted. Allowed values are:
blank or H-source variable values in a continuous distribution,
for scalar variables only
L-discrete source variable values

S-distribution numbers
T = values of the dependent variable follow values of the independent
variable, which must be a discrete scalar variable
Ii = values of the independent variable
Ji = values of the dependent variable
Q = distribution numbers follow values of the independent variable,
which must be a scalar variable
Vi = monotonically increasing set of values of the independent variable
Si = distribution numbers for the dependent variable
Default: DSnH J1 ... Jk
The DS card is used instead of the SI card for a variable that depends on another source variable,
as indicated on the SDEF card.
```

关键短语：

- `Dependent Source Distribution Card`

- `how the Ji are to be interpreted`

- `blank or H-source variable values in a continuous distribution`

- `L-discrete source variable values`

- `S-distribution numbers`

- `values of the dependent variable follow values of the independent variable`

- `distribution numbers follow values of the independent variable`

- `monotonically increasing set of values of the independent variable`

- `distribution numbers for the dependent variable`
