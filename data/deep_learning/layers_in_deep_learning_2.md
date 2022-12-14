## Batch normalization

The distribution of the inputs to deep network may change after each mini-batch when the weights are updated. This can cause the learning algorithm to forever chase a moving target. This change in the distribution of inputs to layers in the network is referred to the technical name “internal covariate shift.”

Batch normalization is a technique for training very deep neural networks that standardizes the inputs to a layer for each mini-batch. This has the effect of stabilizing the learning process and dramatically reducing the number of training epochs required to train deep networks.

### Algorithm [Advance]

**Step 1:**

|   |A1 |A2 |.  |   |An |
|---|---|---|---|---|---|
|S1 |1  |   |   |   |   |
|S2 |3  |   |   |   |   |
|.  |5  |   |   |   |   |
|.  |7  |   |   |   |   |
|SM |9  |   |   |   |   |

Lets say we've a mini-batch of a dataset like above with n features and M samples. For any feature there is one activation vector A<sub>i</sub>. ex: for first feature, the activation vector A1 is (1, 3, 5, 7, 9).

**Step 2:**
For each activation vector calculate mean and variance of mini-batch.

$$ \mu _{i} = \frac{1}{M}\sum A_{i} $$
$$ \sigma _{i} = \sqrt{\frac{1}{M}\sum (A _{i} - \mu)^{2}} $$

**Step 3:**
Normalize each activation to have zero mean and unit standard deviation.

$$ \hat{A _{i}} = \frac{A _{i} - \mu _{i}}{\sigma _{i}} $$

**Step 4:**
Unlike input layer which requires all its normalised values to have 0 mean and unit variance, batch normalization allows it's values to be shifted to a different mean and scaled to a different variance.

$$ BN_{i} = \gamma  \odot \hat{A _{i}} + \beta $$

γ and β are trainable parameters. Thus each batch normalization is able to optimally find the best factor for itself.

**Step 5:**
We also keep track of expontial moving average of mean and standard deviation.

$$ \mu _{mov_{i}} = \alpha \mu _{mov_{i}} + (1 - \alpha) \mu _{i} $$

$$ \sigma _{mov_{i}} = \alpha \sigma _{mov_{i}} + (1 - \alpha) \sigma _{i} $$

**Step 6:**
Above steps are for training. Now we see how validation is done.

$$ \hat{A _{i}} = \frac{A _{i} - \mu _{mov _{i}}}{\sigma _{mov _{i}}} $$

$$ B \hat{N_{i}} = \gamma  \odot \hat{A _{i}} + \beta $$
