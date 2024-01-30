### Intuition

Lets say we want to make this function more quadratic since it is overfitting due to it's higher degree-

$$\theta_{0} + \theta_{1}x + \theta_{2}x^{2} + \theta_{3}x^{3} + \theta_{4}x^{4} $$

in that case we would modify the cost function something like this - 

$$J(\theta) = \frac{1}{2m} \sum_{i=1}^{m}(\hat{y}_{i} - y_{i})^{2} + 1000 \theta_{3}^{2} + 1000 \theta_{4}^{2}$$

Now you might be wondering what would happen after adding high coefficients for the cost function! We add two extra terms to inflate the cost of θ3 and θ4 and the model ends up minimizing them to minimize cost function. Does that makes sense? Try reading again to get more intuition of things.

We can add regularization for all the θ in a single summation.

$$J(\theta) = \frac{1}{2m} \sum_{i=1}^{m}(\hat{y}_{i} - y_{i})^{2} + \lambda\sum_{j=1}^{n} \theta_{j}^{2}$$

### Lasso Regression (L1 Regularization)

Lasso (Least absolute shrinkage and selection operator) regression has the following cost function -

$$J(\theta) = \frac{1}{2m} \sum_{i=1}^{m}(\hat{y}_{i} - y_{i})^{2} + \lambda\sum_{j=1}^{n} |\theta_{j}|$$

What sets Lasso Regression apart is its ability to not only fit a model to the data but also perform feature selection simultaneously. By introducing a constraint based on the absolute values of the coefficients, Lasso encourages some coefficients to be exactly zero, effectively excluding certain features from the model. This makes Lasso particularly useful when dealing with high-dimensional datasets where many features may not significantly contribute to the predictive power of the model.

### Ridge Regression (L2 Regularization)

$$J(\theta) = \frac{1}{2m} \sum_{i=1}^{m}(\hat{y}_{i} - y_{i})^{2} + \lambda\sum_{j=1}^{n} \theta_{j}^{2}$$

Also known as Tikhonov regularization, offers a sophisticated solution to the problem of multicollinearity and overfitting. Ridge Regression shrinks the coefficients towards zero while still keeping them non-zero, thereby preventing extreme values and reducing the model's sensitivity to variations in the input data.

This regularization technique is particularly beneficial when dealing with correlated features, as it can help prevent the model from assigning excessively high weights to them, which might lead to overfitting