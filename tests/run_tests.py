#!/usr/bin/env python3
"""
Ejecutor de todos los tests del Laboratorio 3
"""

import unittest
import sys
import os

# Agregar el directorio de tests al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_all_tests():
    """Ejecuta todos los tests disponibles"""
    
    print("=" * 50)
    print("Ejecutando todos los tests del Laboratorio 3")
    print("=" * 50)
    
    # Descubrir y cargar todos los tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Ejecutar tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print("Todos los tests pasaron exitosamente")
    else:
        print(f"{len(result.failures)} tests fallaron, {len(result.errors)} errores")
        print("\nDetalles de fallas:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
        print("\nDetalles de errores:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    print("=" * 50)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
