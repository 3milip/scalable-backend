#include <iostream>
#include <algorithm>
int main() {
    int n, best;
    std::cin >> n >> best;
    for (int i = 1; i < n; i++) {
        int x;
        std::cin >> x;
        best = std::min(best, x);
    }
    std::cout << best << "\n";
}