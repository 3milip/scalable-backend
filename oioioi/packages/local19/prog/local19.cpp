#include <iostream>
int main() {
    int n, s = 0;
    std::cin >> n;
    for (int i = 0; i < n; i++) {
        int x;
        std::cin >> x;
        s += x;
    }
    std::cout << s / n << "\n";
}