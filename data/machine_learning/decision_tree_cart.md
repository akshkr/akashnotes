I've discussed the basics of decision trees and the ID3 algorithm in detail in [this article](decision_tree_id3.md). Take a look to enhance your understanding of this algorithm.

### Introduction

Decision trees, particularly those constructed through the Classification and Regression Trees (CART) algorithm, are fundamental in machine learning. These hierarchical structures consist of nodes, branches, and leaves, where nodes represent decision points based on features, branches denote possible outcomes, and leaves hold final predictions. CART employs a binary splitting process, selecting optimal features and values at each node to minimize Gini impurity for classification tasks or mean squared error for regression. This results in a tree that efficiently categorizes or predicts outcomes. Optionally, pruning can be applied to avoid overfitting. Understanding the CART algorithm is pivotal for anyone delving into machine learning, as it provides a solid foundation for comprehending decision tree construction and its applications.

### Metrics

Gini impurity measures the likelihood of a randomly chosen element being incorrectly classified in a dataset. The goal of the CART algorithm is to minimize the Gini impurity at each node by selecting the feature and split point that leads to the purest subsets.

The Gini impurity is calculated as follows:

$$ Gini = 1 - \sum_{t=0}^{t=1}p_{t}^{2} $$

where 
p_t = number of records with class = t / total number of records

### Implementation

Let us understand this by an example:

This data says whether the day is good for playing golf or not. Decision column is our target variable.

| Day | Outlook  | Temp. | Humidity | Wind   | Decision |
|-----|----------|-------|----------|--------|----------|
| 1   | Sunny    | Hot   | High     | Weak   | No       |
| 2   | Sunny    | Hot   | High     | Strong | No       |
| 3   | Overcast | Hot   | High     | Weak   | Yes      |
| 4   | Rain     | Mild  | High     | Weak   | Yes      |
| 5   | Rain     | Cool  | Normal   | Weak   | Yes      |
| 6   | Rain     | Cool  | Normal   | Strong | No       |
| 7   | Overcast | Cool  | Normal   | Strong | Yes      |
| 8   | Sunny    | Mild  | High     | Weak   | No       |
| 9   | Sunny    | Cool  | Normal   | Weak   | Yes      |
| 10  | Rain     | Mild  | Normal   | Weak   | Yes      |
| 11  | Sunny    | Mild  | Normal   | Strong | Yes      |
| 12  | Overcast | Mild  | High     | Strong | Yes      |
| 13  | Overcast | Hot   | Normal   | Weak   | Yes      |
| 14  | Rain     | Mild  | High     | Strong | No       |

1. Let us calculate Gini indexes for Outlook feature

$$ Gini (Outlook=Sunny) = 1 - (\frac{2}{5})^2 - (\frac{3}{5})^2 = 0.48$$
2/5 means 2 out of total 5 sunny days have decision No and 3/5 means 3 out of total 5 sunny days have decision Yes. Similarly
$$ Gini (Outlook=Overcast) = 1 - (\frac{4}{4})^2 - (\frac{0}{4})^2 = 0$$
$$ Gini (Outlook=Rain) = 1 - (\frac{3}{5})^2 - (\frac{2}{5})^2 = 0.48$$

Now we just take weighted average of Gini-index of the feature outlook and weight would be the fraction of that value of the feature.

$$ Gini(Outlook) = p_{sunny} * Gini(sunny) + p_{overcast} * Gini(overcast) + p_{rain}*Gini(rain)$$

$$ Gini(Outlook) = \frac{5}{14} * 0.48 + \frac{4}{14} * 0 + \frac{5}{14} * 0.48 = 0.342$$
 
 Similarly we can calculate Gini for other features - 

 Gini(Temp) = 0.439
 Gini(Humidity) = 0.367
 Gini(Wind) = 0.428

 2. Select the feature with the minimum Gini impurity as the splitting node.
 Outlook (0.342) is our splitting node.

![CART](/data/assets/machine_learning/cart_1.png)
all the samples in overcast have decision as Yes.

3. For the sunny and rain outlook condition follow the same algorithm with data sample only for sunny/rain outlook condition.

Finally the tree might look something like this.
![CART2](/data/assets/machine_learning/cart_2.png)
