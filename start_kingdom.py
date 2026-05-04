from commander.kernel import Kernel
from kingdom_setup import setup

def main():
    config = setup()
    kernel = Kernel(config)
    kernel.start()

if __name__ == "__main__":
    main()
