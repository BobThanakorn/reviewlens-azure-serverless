Written by hand after reading the 2026-11-26 run (500 reviews, `gpt-5-nano`, `reasoning_effort=minimal`). `scripts/evaluate.py` embeds this file; update it when the numbers change.

**Most errors are positive vs neutral, not wrong polarity.** 99 of the 113 errors (88%) sit on the positive/neutral border: 54 four- or five-star reviews labelled neutral and 45 three-star reviews labelled positive. Only one review crossed from negative stars to a positive label, and no positive-star review was labelled negative.

**The star rating is often the noisy side.** Examples 1 and 5 above read as clearly positive (good food, quiet room, good service; a rich soup that needs no seasoning) but carry 3 and 2 stars. Example 4 is a 3-star review whose text complains about rude staff, so `negative` is a defensible label. Thai reviewers on Wongnai often give 3 stars to a pleasant but unremarkable visit, which this mapping (3 = neutral) treats as ground truth.

**Long, descriptive reviews pull the model towards neutral.** Examples 2 and 3 spend most of their text on directions, the menu and history, with the opinion in one or two sentences. The model summarised them as mixed ("overall not outstanding"; "less tasty than before, but the pork is still good") and chose neutral.

**What would improve it.** Few-shot examples of short positive 3-star reviews and of long descriptive 4-star reviews; asking the model for a 1-5 score and mapping it, instead of three classes; a human-labelled subset to separate model error from rating noise. Three rows failed or returned invalid output and count as wrong; they are small enough not to change the picture.
