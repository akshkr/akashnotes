Logistic regression is a statistical method used to model the probability of a certain outcome or event occurring based on a set of input variables. It is mostly used in classification tasks. Then why is it called regression? Because It doesn't predict a class; rather, it predicts the probability of a data point belonging to a class.

### Hypothesis function

$$ \hat{y} = h_{\theta}(x) = g(\theta^{T}x) $$

where:
$$g(z) = \frac{1}{1+e^{-z}} $$

this function is called sigmoid function or logistic function. To better comprehend the hypothesis function of logistic regression, let's break it down. The term θ^Tx, which is analogous to linear regression, represents the weighted sum of the input variables. However, in logistic regression, the sigmoid function is applied to this sum to transform it into a suitable form.

The sigmoid function plays a crucial role in logistic regression by squashing the output to a range between 0 and 1, allowing it to represent a probability.

![sig](/data/assets/deep_learning/sig.jpg)

### Cost function

$$ BCE = -\frac{1}{n}\sum_{i=1}^{n}Cost(\hat{y}, y) = -\frac{1}{n}\sum_{i=1}^{n}y_{i}log(\hat{y_{i}}) + (1 - y_{i})log(1 - \hat{y_{i}}) $$

The cost function in logistic regression, also known as the log loss or binary cross-entropy loss, is used to evaluate the performance of the model and determine how well it predicts the binary outcomes. The goal is to minimize the cost function to obtain the optimal set of model parameters.

Lets break and understand the cost function.

$$ Cost(y) = 
\begin{cases}
 -log(\hat{y_{i}})& \text{ if } y= 1\\ 
 -log(1 - \hat{y_{i}})& \text{ if } y= 0
\end{cases} $$

![logy](/data/assets/deep_learning/logy.png)
![log1-y](/data/assets/deep_learning/log1-y.png)

After plotting the cost function for both the values of y, observe that the cost is higher when predicted y is closer to 0 and actual y is closer to 1 and similarly when actual y = 0, the cost is high when prediction is close to 1.