#include <iostream>
int main() {
    int a, b, c;
    std::cin >> a >> b >> c;
    std::cout << (a + b > c && a + c > b && b + c > a ? "TAK" : "NIE") << "\n";
}