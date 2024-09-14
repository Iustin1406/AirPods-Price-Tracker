# AirPods Price Tracker

## Overview
This Python script tracks the prices of AirPods from two online retailers, Altex and Flanco. It fetches data on AirPods listings, compares prices to historical averages, and sends email notifications if a good offer is found.

## Features
- Extracts product data from Altex and Flanco websites.
- Calculates the cheapest models of AirPods.
- Computes average prices for different AirPods models over the past month.
- Sends email notifications for significant price drops.

## Requirements
- Python 3.x
- Selenium
- `python-dotenv`
- `requests` (for potential future extensions)
- Access to a Gmail account (for sending emails)