#include <iostream>
int main() {
    long long a, b, w = 1;
    std::cin >> a >> b;
    for (int i = 0; i < b; i++) w *= a;
    std::cout << w << "\n";
}