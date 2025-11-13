#!/usr/bin/env python3
"""
Simple Google Maps Data Extractor
Just run this file and input the URL when prompted
"""

import json
import sys
from datetime import datetime
from extractor import GoogleMapsExtractor

def print_separator(char="-", length=60):
    """Print a separator line"""
    print(char * length)

def print_header():
    """Print application header"""
    print("\n" + "=" * 60)
    print("       GOOGLE MAPS BUSINESS DATA EXTRACTOR")
    print("=" * 60)
    print()

def validate_url(url):
    """Check if URL is a valid Google Maps URL"""
    valid_patterns = ['google.com/maps', 'maps.google.com', 'goo.gl/maps']
    return any(pattern in url.lower() for pattern in valid_patterns)

def display_results(data):
    """Display extraction results in a formatted way"""
    print("\n" + "=" * 60)
    print("                    EXTRACTION RESULTS")
    print("=" * 60)
    
    # Check for errors
    if 'error' in data:
        print(f"\n❌ ERROR: {data['error']}")
        return
    
    # Display basic information
    print("\n📊 BUSINESS INFORMATION:")
    print_separator()
    print(f"📍 Name:           {data.get('name', 'Not found')}")
    print(f"📮 Address:        {data.get('address', 'Not found')}")
    print(f"📞 Phone:          {data.get('phone', 'Not found')}")
    print(f"🌐 Website:        {data.get('website', 'Not found')}")
    print(f"⭐ Rating:         {data.get('rating', 'Not found')}")
    print(f"📝 Total Reviews:  {data.get('total_reviews', 'Not found')}")
    print(f"📅 First Review:   {data.get('first_review_date', 'Not found')}")
    
    # Display negative reviews
    negative_reviews = data.get('recent_negative_reviews', [])
    
    print(f"\n👎 NEGATIVE REVIEWS FOUND: {len(negative_reviews)}")
    print_separator()
    
    if negative_reviews:
        for i, review in enumerate(negative_reviews, 1):
            print(f"\n[Review #{i}]")
            print(f"Rating: {review.get('rating', 'N/A')} | Date: {review.get('date', 'Unknown')}")
            
            # Format review text
            text = review.get('text', '')
            if len(text) > 200:
                text = text[:200] + "..."
            print(f"Comment: {text}")
            
            if i < len(negative_reviews):
                print("-" * 40)
    else:
        print("No negative reviews found or unable to extract reviews.")
    
    print("\n" + "=" * 60)

def save_to_file(data, url):
    """Save results to a JSON file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"google_maps_extract_{timestamp}.json"
    
    output_data = {
        'extraction_date': datetime.now().isoformat(),
        'source_url': url,
        'results': data
    }
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Results saved to: {filename}")
        return True
    except Exception as e:
        print(f"\n❌ Failed to save file: {str(e)}")
        return False

def main():
    """Main function"""
    try:
        # Print header
        print_header()
        
        # Keep running until user decides to exit
        while True:
            # Get URL from user
            print("Enter Google Maps URL (or type 'quit' to exit):")
            url = input("► ").strip()
            
            # Check if user wants to quit
            if url.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                sys.exit(0)
            
            # Validate URL
            if not url:
                print("\n❌ URL cannot be empty! Try again.\n")
                continue
            
            if not validate_url(url):
                print("\n❌ Invalid URL! Please provide a valid Google Maps URL.")
                print("Example: https://www.google.com/maps/place/...\n")
                continue
            
            # Extract data
            print("\n⏳ Extracting data from Google Maps...")
            print("This may take a few seconds...\n")
            
            extractor = GoogleMapsExtractor()
            results = extractor.get_place_details(url)
            
            # Display results
            display_results(results)
            
            # Ask if user wants to save results
            print("\nDo you want to save the results to a JSON file? (y/n):")
            save_choice = input("► ").strip().lower()
            
            if save_choice == 'y':
                save_to_file(results, url)
            
            # Ask if user wants to extract another URL
            print("\nDo you want to extract another URL? (y/n):")
            continue_choice = input("► ").strip().lower()
            
            if continue_choice != 'y':
                print("\n👋 Thank you for using Google Maps Extractor!")
                break
            
            print("\n" + "=" * 60 + "\n")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()