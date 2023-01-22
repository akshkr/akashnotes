## Batch normalization

The distribution of the inputs to a deep network may change after each mini-batch when the weights are updated. This can cause the learning algorithm to forever chase a moving target. This change in the distribution of inputs to layers in the network is referred by the technical name “internal covariate shift.”

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

Let's say we've got a mini-batch of a dataset like this table with n features and M samples. For any feature, there is one activation vector Ai. ex: for the first feature, the activation vector A1 is (1, 3, 5, 7, 9) for M (5) samples.

**Step 2:**
For each activation vector, calculate the mean and variance of the mini-batch.

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


### Why does Batch Normalization work?

**Theory 1: Covariate shift**

Sometimes the model is fed data with a very different distribution than it was previously trained with, even though the data still conforms to the same target function.

Now the model will have to re-learn some of it's features according to the new target. This slows down the training process. In other words, each layer ends up trying to learn from a constantly shifting input.

**Theory 2: Loss and gradient smoothening**

In typical neural network loss landscape isn't a smooth convex surface. It has sharp cliffs and flat surfaces. Thus, gradient descent could encounter an obstacle in what it thought was a promising direction to follow.

Batch normalization smoothens the loss landscape substantially by changing the distribution on network weights.

### Advantages

1. Model converges faster and speeds up training.
2. Less sensitive to how weights are initialized and precise tuning of hyper-parameters.
3. We can increase the learning rate because batch norm reduces effect of outlier gradient.
4. Adds regularization to training.

### Disadvantages
Doesnn't work for small size batches. Result has too much noise in mean and variance.

### References
- [Batch normalization](https://arxiv.org/abs/1502.03167)