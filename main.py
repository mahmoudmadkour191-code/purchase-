# MCV Screen Detector Code

import cv2
import numpy as np

class ScreenDetector:
    def __init__(self):
        self.model = cv2.CascadeClassifier('path_to_classifier')  # Load your classifier here

    def detect(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        screens = self.model.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        return screens

if __name__ == '__main__':
    screen_detector = ScreenDetector()
    image = cv2.imread('path_to_image')  # Load your image
    screens = screen_detector.detect(image)
    for (x, y, w, h) in screens:
        cv2.rectangle(image, (x, y), (x + w, y + h), (255, 0, 0), 2)  # Draw rectangles
    cv2.imshow('Detected Screens', image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()