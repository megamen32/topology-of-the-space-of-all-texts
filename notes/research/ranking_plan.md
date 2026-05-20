# Human-ordered enumeration plan
Current:
page -> cost(page)
Next:
rank(page)=count(all pages with lower cost)
Approach:
1. Weighted automaton over cluster transitions
2. Dynamic programming count(cost<X,length=L)
3. Arithmetic-coding style rank/unrank
Result:
Strict bijection preserved + human-like pages near rank 0
