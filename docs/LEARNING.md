# Study guide

Plain-language notes on every concept used in HabitatShift. Each entry says what it is, why it is used here, and
what someone might ask you about it. Version 3 concepts are added as they are used (see the end of this file).

How to use it: read an entry, then open the code or result it points to, then try to explain it aloud without
looking. If you cannot, that entry needs another pass.

---

## Part 1: Satellite basics

### Bands and reflectance
A satellite camera records light in separate wavelength ranges called bands (blue, green, red, near-infrared,
shortwave-infrared). Reflectance is the fraction of sunlight a surface sends back in a band, from 0 to 1. Different
surfaces reflect differently: water is dark in near-infrared, healthy leaves are bright in it, concrete is bright in
shortwave-infrared. All the indices below exploit those differences.
*Ask yourself:* why is vegetation bright in near-infrared but dark in red?

### Sentinel-2 L2A and Sen2Cor
Sentinel-2 is an EU satellite pair that images land every ~5 days at 10 m (some bands 20 m). L2A means the data
is corrected for the atmosphere to estimate surface reflectance; Sen2Cor is the ESA software that does it.
*Ask yourself:* why correct for the atmosphere before comparing two dates?

### SCL cloud mask
The Scene Classification Layer labels each pixel (cloud, shadow, snow, water, vegetation...). We use it to throw
away unusable pixels before computing anything. A pixel is only compared if it was clear on every date used.

### STAC and COGs
STAC is a standard way to search satellite catalogues by place and date. A COG (Cloud Optimised GeoTIFF) is an
image file organised so you can download just a small window instead of the whole scene. Together they let us read
only our small study area from huge public archives.

---

## Part 2: Spectral indices (the V2 change signal)

An index combines bands into one number that highlights something.

| Index | Formula idea | Highlights |
|---|---|---|
| NDVI | (NIR - Red) / (NIR + Red) | green vegetation |
| NDWI | (Green - NIR) / (Green + NIR) | open water |
| MNDWI | (Green - SWIR) / (Green + SWIR) | water, less confused with built-up |
| NDBI | (SWIR - NIR) / (SWIR + NIR) | built-up land |
| NDSI | (Green - SWIR) / (Green + SWIR) | snow and ice |

Dividing by the sum cancels some brightness differences (lighting, haze), which is why ratios are used instead of
raw bands.
*Ask yourself:* why do MNDWI and NDSI share a formula, and how do you tell water from snow with it?

### Compositing
Taking several clear scenes in a period and combining them (usually the median) into one cleaner image. The median
ignores stray cloud or haze in a single scene.

---

## Part 3: Change detection and noise (the core idea of V2)

### Change as a difference
Change = index(after) - index(before), pixel by pixel. The trouble: even with no real change, two dates differ
because of haze, sun angle, soil moisture and sensor noise.

### Noise and the standard error
In each period we have several scenes. The spread between them says how much a pixel wobbles by itself. The
standard error (SE) is that spread scaled by how many scenes we averaged. Rule used here: count a pixel as changed
only if the difference exceeds **3 x SE**. This is the single most important idea in the project, and version 3
reuses it as a fair yardstick for comparing methods.
*Ask yourself:* what happens to false alarms if you use 1 x SE? What happens to missed real change at 5 x SE?

### Threshold sweeps
Trying many thresholds instead of one and showing how the result moves. It exposes how much a headline number
depends on an arbitrary choice.

### Minimum mapping unit
The smallest patch of changed pixels worth reporting. Single isolated pixels are usually noise, so they are
dropped.

### Resolution sensitivity (10 m vs 20 m)
Re-running at coarser resolution to see whether a result survives. A finding that vanishes at 20 m depended on
fine detail that may not be reliable.

---

## Part 4: Statistics for spatial data

### Confidence intervals and block bootstrap
A confidence interval says how much a number could move if we drew a different sample. A plain bootstrap
resamples pixels, but neighbouring pixels are alike, so that overstates certainty. The **block** bootstrap
resamples whole spatial blocks to respect that.

### Spatial autocorrelation
Nearby places are more similar than distant ones. Consequence: pixels are not independent samples, which affects
confidence intervals and train/test splits.

### Spatial block cross-validation
When tuning or training, split by geographic blocks so test pixels are not neighbours of training pixels.
Otherwise the score looks great because the model is partly memorising the neighbourhood.
*Ask yourself:* why does a random pixel split inflate accuracy for satellite images?

---

## Part 5: Reference data and agreement

### Why "agreement", not "accuracy"
Hansen forest loss, ESA WorldCover and the like are other products with their own errors, not ground truth. When
we compare against them we measure agreement. Saying "accuracy" would claim the reference is perfect.

### Hansen Global Forest Change
A global 30 m map of yearly tree-cover loss. Used in V2 to check forest-loss detection in the Western Ghats.

### ESA WorldCover
A 10 m land-cover map of 11 classes. Used as the reference for the Random Forest experiment.

---

## Part 6: Machine learning used in V2

### Random Forest
Many decision trees, each trained on a random sample of data and features, voting on the answer. Robust and fast,
but it only learns patterns in the labels it is given.
*Honest note:* in V2 the labels came from WorldCover, so the model largely learned to copy another model. That is
why V3 moves to a better-posed question.

### Class imbalance and macro-F1
If 95% of pixels are "no change", always guessing "no change" scores 95% overall agreement and is useless.
Precision is how many flagged pixels were right; recall is how many true ones were found; F1 combines them;
**macro**-F1 averages F1 across classes so rare classes count equally.

---

## Part 7: Time series

### Seasonal fit (harmonic regression)
Vegetation and water follow a yearly cycle. Fitting sine and cosine terms models that cycle; what is left after
subtracting it (the residual) is where unusual change shows up. Used for Kathmandu and the Western Ghats.

---

## Part 8: Reproducibility
Seeds, pinned dependency versions, checksums of outputs, and a fresh-environment rerun. V2 verified that the
pipeline reproduces its results byte for byte. In V3 this extends to model weights (record the hash).

---

## Version 3 concepts: radar and lakes (Phase 1)

### Synthetic aperture radar (SAR) and backscatter
Sentinel-1 sends its own microwave pulses and measures how much comes back (backscatter). It works at night and
through cloud, which matters in the monsoon. Calm water reflects the pulse away from the satellite, so it looks
dark; rough or built-up land looks bright. VV and VH are two polarisations (vertical-vertical, vertical-horizontal).
Values are usually converted to decibels (dB = 10 x log10 of power), because backscatter spans orders of magnitude.
*Ask yourself:* why can wind or ice make a lake look bright to radar?

### Speckle and the Lee filter
Radar images have grain-like noise called speckle, caused by waves adding up randomly. A Lee filter smooths it
inside uniform areas but keeps edges, by blending each pixel with its local mean according to how much local
variation exceeds what speckle alone would give.

### Terrain correction, shadow and layover
Radar looks sideways. On steep slopes facing away, the slope is in shadow (dark, looks like water). On slopes facing
the satellite, the top is imaged before the base (layover), which can make a lake look bright. RTC data corrects
brightness for terrain, but layover and shadow remain. In this project one orbit at Tsho Rolpa could not see the
lake at all (lake -7 dB, same as land), while two others saw it at -15 to -17 dB. We screen orbits per lake and
list what was left out.

### Otsu thresholding
A way to split a histogram into two groups (water and land) by choosing the value that best separates their
means. It works when the histogram has two humps; the threshold is clamped to a plausible range and flagged when it
had to be.

### DEM and slope
A digital elevation model gives height per pixel (Copernicus GLO-30, 30 m). Slope from the DEM excludes terrain
where radar shadow looks like water. Flat DEM areas also locate a lake: lake surfaces are flat in the DEM.

### The lake "seed"
The flat DEM area nearest the lake point. Only water patches that touch the seed count, so nearby ponds and shadow
patches are ignored. The seed is not used to set the water threshold, so a lake that shrinks or drains still shows
it.

### Scene screening versus honest gaps
Scenes are excluded when the lake is not dark (ice, wind, melt), when the orbit cannot see it, when the scene is too
cloudy, or in the frozen season. Every exclusion is counted and shown, never silently dropped.

### Median and standard error per month
Several scenes per month give a spread; the standard error is the spread divided by the square root of the count.
A month-to-month change is flagged only if it exceeds 3 times the combined standard error, the same rule as in
version 2. It only captures random scene-to-scene scatter, not systematic differences such as radar vs optical.

### Hi-MAG and "agreement"
Hi-MAG is an annual 30 m glacial lake outline dataset (2008-2017), itself made from Landsat. Comparing with it
measures agreement with another product.

### Pilot findings worth remembering
Radar vs Hi-MAG in 2017: Tsho Rolpa -5.5%, Imja Tsho +1.3%, Thulagi -33%. Optical: +2.4%, -27%, -7%. Optical fails
at turbid, icy Imja Tsho (the water rule assumes dark, clear water); radar underestimates at steep Thulagi. So
neither sensor is simply better.

## Version 3 concepts: foundation models (Phase 2)

### Embeddings and cosine distance
A foundation model turns each 16 x 16 pixel patch of an image into a vector of 1024 numbers that summarises what is
there. Two patches are compared with cosine distance (1 minus the cosine of the angle between the vectors), which
ignores vector length.

### Prithvi-EO-2.0
An open NASA/IBM Vision Transformer trained with masked autoencoding on Harmonized Landsat Sentinel-2 imagery. We
use only the encoder, one scene at a time, with six bands (blue, green, red, narrow NIR, SWIR1, SWIR2), in fp16.

### Noise calibration for vectors
For each patch: noise variance from pairs of scenes in the same period, change = distance between period means,
and z = change divided by the noise expected for that many scenes. z is about 1 when nothing changed, for any
vector length. Because 3 scenes give few pairs, the noise estimate is pooled over a 3 x 3 patch neighbourhood.

### Average precision, ROC-AUC and recall at a false-positive rate
Rank every patch by its change score, then compare with the reference labels. Average precision is the area under
the precision-recall curve; a random score gets the base rate (the share of positives), so it is the right yardstick
when positives are rare. ROC-AUC is the chance a random positive outranks a random negative. Recall at 5% false
positives asks how much real change is found when only 5% of clean patches may be flagged. Prefer these to one
threshold, because they show the whole trade-off.

### Spatial block bootstrap, paired
Resample whole map blocks (not single patches) to see how much a metric would move on a different draw of area, then
compare two methods on the same resamples. If the interval of their difference excludes zero, the gap is unlikely
to be chance.

### Directional baselines
A distance (cosine, Euclidean) has no sign. Forest loss lowers NDVI, so the fair baseline for loss is the signed
NDVI decrease, not the unsigned difference. Comparing a signed method against unsigned ones would flatter the
unsigned one's loss.

### Linear probing versus embeddings as features
Here embeddings are used as they come, with no training, so any gap to simple baselines is the model's own
representation and not a tuned classifier. A trained head might do better; that is a different experiment.

### Placebo test
Compare one scene with the rest of its own period. Nothing changed, so every flag is a false alarm. Prithvi raised
0 to 3.4% false alarms at z > 3 across twelve areas (medians under 0.5%), indices and raw bands up to 41% (medians 3 to 13%). This is calibration, not detection skill.
Real evaluation needs reference change data at a matched false-alarm rate.

## Version 3 concepts (filled in as each one is used)

These are listed in the plan; each gets a full entry when its phase starts.

- GPU setup: CUDA, PyTorch, fp16 and memory (**done in Phase 0**, see below)
- Synthetic aperture radar: backscatter, VV/VH, dB, speckle, terrain correction, shadow and layover
- Otsu thresholding, DEMs and slope
- Foundation models: self-supervised learning, masked autoencoders, vision transformers
- Embeddings and cosine distance; signal-to-noise calibration
- PR-AUC vs ROC-AUC
- U-Net, Dice and BCE loss, weak supervision, label noise
- Spatial and temporal hold-out
- Conformal prediction: split conformal, coverage

### GPU setup (Phase 0)
PyTorch is the deep-learning library. It needs a build compiled for your GPU's CUDA version. The RTX 5050 is a
newer "Blackwell" chip (compute capability 12.0), which older PyTorch builds do not support; we installed the
CUDA 12.8 build (`torch 2.11.0+cu128`) and verified it. **fp16** means 16-bit numbers instead of 32-bit: about
half the memory and faster, with small precision loss that is fine for inference. The 8 GB of VRAM is the limit
that shapes batch sizes and which models fit. The first GPU run is slow because kernels are set up once; time the
second run.
*Ask yourself:* why does an 8 GB card limit batch size more than model choice for a 300M-parameter model?

## Phase 3: a small trained model (U-Net) with honest uncertainty

- **Semantic segmentation**: label every pixel (water or not) rather than one label per image.
- **U-Net**: a network that shrinks the image to see context, then expands it back, passing early detail across
  shortcuts ("skip connections") so edges stay sharp. Good for small datasets.
- **Weak labels**: training targets from a rule (here the optical water index) instead of hand drawing. The model can
  only be as right as the rule, so scores mean agreement with the rule.
- **BCE + Dice loss**: binary cross-entropy scores each pixel; Dice scores overlap of the whole mask, which keeps a model
  from predicting "no water" everywhere when lakes are a small part of the image. Both are counted only on valid pixels.
- **IoU**: overlap divided by union of predicted and reference water. 1 is a perfect match.
- **Splitting by lake and by time**: neighbouring pixels and dates are alike, so a random split leaks. Hold out whole
  lakes (new places) and a later year (new dates) separately; the two scores answer different questions.
- **Split conformal prediction**: turn predicted area into an interval. Measure the model's errors on a calibration set,
  take a high quantile of them, and add that much margin to new predictions. The coverage guarantee holds only if
  calibration and test data are exchangeable, which fails when test lakes differ from calibration lakes.
- **Coverage**: how often the true value falls inside the interval. Check it on data not used to calibrate.
- **Cross-validation over lakes**: split the lakes into folds, train on all but one fold, predict the held-out fold, and
  repeat. Every lake is then predicted by a model that never saw it, and calibration can use many lakes instead of four.
- **Marginal vs per-lake coverage**: conformal guarantees hold on average over the data, not for each lake. A method can
  cover 87% of all areas yet fail completely for a few lakes.
