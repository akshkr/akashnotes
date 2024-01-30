A decision tree is a tree-like structure where each internal node represents a test on a specific attribute, each branch represents the outcome of the test or decision, and each leaf node represents a class label or a numerical value.


Here is a basic decision tree showing how it might classify whether a patient has low or high heart attack risk according to different attributes.

![Decision tree](/data/assets/machine_learning/decision_tree_for_heart_attack.png)

There are many types of decision tree algorithm but we will be focusion on two of the most prominent ones:

1. ID3 (Iterative Dichotomiser 3):
ID3 was one of the earliest decision tree algorithms developed by Ross Quinlan. It uses entropy and information gain to determine the best split at each node.

2. CART (Classification and Regression Trees):
CART is a versatile decision tree algorithm introduced by Leo Breiman. It can be used for both classification and regression tasks. For classification, it uses Gini impurity, and for regression, it uses mean squared error to determine the best splits.

Lets first try to understand the ID3 algorithm using an example:

## ID3 

### Introduction

ID3 stands for Iterative Dichotomiser 3 and is named such because the algorithm iteratively (repeatedly) dichotomizes(divides) features into two or more groups at each step.

ID3 uses a top-down greedy approach to build a decision tree. In simple words, the top-down approach means that we start building the tree from the top and the greedy approach means that at each iteration we select the best feature at the present moment to create a node.

Most generally ID3 is only used for classification problems with nominal features only.

Let's take a COVID-19 sample data to understand this algorithm better. The target column is Infected - YES/NO and the columns to make decisions are Fever, Cough and Breathing issues.

```
+----+-------+-------+------------------+----------+
| ID | Fever | Cough | Breathing issues | Infected |
+----+-------+-------+------------------+----------+
| 1  | NO    | NO    | NO               | NO       |
+----+-------+-------+------------------+----------+
| 2  | YES   | YES   | YES              | YES      |
+----+-------+-------+------------------+----------+
| 3  | YES   | YES   | NO               | NO       |
+----+-------+-------+------------------+----------+
| 4  | YES   | NO    | YES              | YES      |
+----+-------+-------+------------------+----------+
| 5  | YES   | YES   | YES              | YES      |
+----+-------+-------+------------------+----------+
| 6  | NO    | YES   | NO               | NO       |
+----+-------+-------+------------------+----------+
| 7  | YES   | NO    | YES              | YES      |
+----+-------+-------+------------------+----------+
| 8  | YES   | NO    | YES              | YES      |
+----+-------+-------+------------------+----------+
| 9  | NO    | YES   | YES              | YES      |
+----+-------+-------+------------------+----------+
| 10 | YES   | YES   | NO               | YES      |
+----+-------+-------+------------------+----------+
| 11 | NO    | YES   | NO               | NO       |
+----+-------+-------+------------------+----------+
| 12 | NO    | YES   | YES              | YES      |
+----+-------+-------+------------------+----------+
| 13 | NO    | YES   | YES              | NO       |
+----+-------+-------+------------------+----------+
| 14 | YES   | YES   | NO               | NO       |
+----+-------+-------+------------------+----------+
```

### Metrics

ID3 uses Information Gain or just Gain to find the best feature.

Information Gain calculates the reduction in the entropy and measures how well a given feature separates or classifies the target classes. The feature with the highest Information Gain is selected as the best one.

In the case of binary classification (where the target column has only two types of classes) entropy is 0 if all values in the target column are homogenous(similar) and will be 1 if the target column has equal number values for both the classes.

$$ Entropy(S) = -\sum_{i=1}^{n} p_{i} * log_{2}(p_{i}) $$

where 

S : dataset</br>
n: total number of classes
p_i: probability of class i or ratio of “number of rows with class i in the target column” to the “total number of rows” in the dataset.

Information gain for a column A is calculated as:

$$IG(S, A) = Entropy(S) - \sum\frac{|S_{v}|}{|S|} * Entropy(S_{v})$$

where Sᵥ is the set of rows in S for which the feature column A has value v, |Sᵥ| is the number of rows in Sᵥ and likewise |S| is the number of rows in S.

### Algorithm

1. Calculate the Information Gain of each feature.
2. Considering that all rows don’t belong to the same class, split the dataset S into subsets using the feature for which the Information Gain is maximum.
3. Make a decision tree node using the feature with the maximum Information gain.
4. If all rows belong to the same class, make the current node as a leaf node with the class as its label.
5. Repeat for the remaining features until we run out of all features, or the decision tree has all leaf nodes.

### Implementation

Now let us look at our dataset and see how we can construct decision tree.

1. Calculate the Information Gain of each feature.

IG calculation for Fever:
In this feature there are 8 rows having value YES and 6 rows having value NO.
As shown below, in the 8 rows with YES for Fever, there are 6 rows having target value YES and 2 rows having target value NO.

```
+-------+-------+------------------+----------+
| Fever | Cough | Breathing issues | Infected |
+-------+-------+------------------+----------+
| YES   | YES   | YES              | YES      |
+-------+-------+------------------+----------+
| YES   | YES   | NO               | NO       |
+-------+-------+------------------+----------+
| YES   | NO    | YES              | YES      |
+-------+-------+------------------+----------+
| YES   | YES   | YES              | YES      |
+-------+-------+------------------+----------+
| YES   | NO    | YES              | YES      |
+-------+-------+------------------+----------+
| YES   | NO    | YES              | YES      |
+-------+-------+------------------+----------+
| YES   | YES   | NO               | YES      |
+-------+-------+------------------+----------+
| YES   | YES   | NO               | NO       |
+-------+-------+------------------+----------+
```
As shown below, in the 6 rows with NO, there are 2 rows having target value YES and 4 rows having target value NO.

```
+-------+-------+------------------+----------+
| Fever | Cough | Breathing issues | Infected |
+-------+-------+------------------+----------+
| NO    | NO    | NO               | NO       |
+-------+-------+------------------+----------+
| NO    | YES   | NO               | NO       |
+-------+-------+------------------+----------+
| NO    | YES   | YES              | YES      |
+-------+-------+------------------+----------+
| NO    | YES   | NO               | NO       |
+-------+-------+------------------+----------+
| NO    | YES   | YES              | YES      |
+-------+-------+------------------+----------+
| NO    | YES   | YES              | NO       |
+-------+-------+------------------+----------+
```

Entropy of dataset:
$$ Entropy(S) = - \frac{8}{14} * log_{2}(\frac{8}{14}) - \frac{6}{14} * log_{2}(\frac{6}{14})$$

Information gain for fever:

```
total rows
|S| = 14

For v = YES, |Sᵥ| = 8
Entropy(Sᵥ) = - (6/8) * log₂(6/8) - (2/8) * log₂(2/8) = 0.81

For v = NO, |Sᵥ| = 6
Entropy(Sᵥ) = - (2/6) * log₂(2/6) - (4/6) * log₂(4/6) = 0.91

# Expanding the summation in the IG formula:
IG(S, Fever) = Entropy(S) - (|Sʏᴇꜱ| / |S|) * Entropy(Sʏᴇꜱ) - 
(|Sɴᴏ| / |S|) * Entropy(Sɴᴏ)

∴ IG(S, Fever) = 0.99 - (8/14) * 0.81 - (6/14) * 0.91 = 0.13
```
Similarly we can calculate IG for 

```
IG(S, Cough) = 0.04
IG(S, BreathingIssues) = 0.40
```

Here we can see that Breathing issue feature has higher information gain thus we can split our dataset using this feature at the root node.
After split this is what our tree will look like:

![Decision tree](/data/assets/machine_learning/decision_tree_1.png)

Now we take the left node (with Breathing issue as YES) and calculate the same for remaining features (Cough and Fever). Note that the data in the left node will only be for the rows with Breathing issue as YES.

```
IG(Sʙʏ, Fever) = 0.20
IG(Sʙʏ, Cough) = 0.09
```

IG of Fever is greater than that of Cough, so we select Fever as the left branch of Breathing Issues:

Our tree now looks like this:

![Decision tree](/data/assets/machine_learning/decision_tree_2.png)

Next, we find the feature with the maximum IG for the right branch of Breathing Issues. But, since there is only one unused feature left we have no other choice but to make it the right branch of the root node.
So our tree now looks like this:

![Decision tree](/data/assets/machine_learning/decision_tree3.png)

For the leaf nodes, we just take the mode of the data at every leaf node and assign the labels.

For the left leaf node of Fever, we see the subset of rows from the original data set that has Breathing Issues and Fever both values as YES.

```
+-------+-------+------------------+----------+
| Fever | Cough | Breathing issues | Infected |
+-------+-------+------------------+----------+
| YES   | YES   | YES              | YES      |
+-------+-------+------------------+----------+
| YES   | NO    | YES              | YES      |
+-------+-------+------------------+----------+
| YES   | YES   | YES              | YES      |
+-------+-------+------------------+----------+
| YES   | NO    | YES              | YES      |
+-------+-------+------------------+----------+
| YES   | NO    | YES              | YES      |
+-------+-------+------------------+----------+
```

Since all the values in the target column are YES, we label the left leaf node as YES, but to make it more logical we label it Infected.

After doing the same for all the leaves this is what the final tree looks like - 

![Decision tree](/data/assets/machine_learning/decision_tree4.png)

The right node of Breathing issues is as good as just a leaf node with class ‘Not infected’. This is one of the Drawbacks of ID3, it doesn’t do pruning.

Pruning is a mechanism that reduces the size and complexity of a Decision tree by removing unnecessary nodes.