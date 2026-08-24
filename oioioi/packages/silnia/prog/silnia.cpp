#include <iostream>
int main() {
    int n;
    std::cin >> n;
    long long w = 1;
    for (int i = 1; i <= n; i++) w *= i;
    std::cout << w << "\n";
}