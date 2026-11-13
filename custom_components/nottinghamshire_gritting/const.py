"""Constants for Nottinghamshire Gritting."""

DOMAIN = "nottinghamshire_gritting"
NAME = "Nottinghamshire Gritting"

EVENT_IMAP_CONTENT = "imap_content"
SIGNAL_UPDATE = f"{DOMAIN}_update"

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.decision"

SOURCE_COUNTY_X = "county_x"
SOURCE_COUNTY_EMAIL = "county_email"
SOURCE_CITY_EMAIL = "city_email"

SOURCE_PRIORITY = (
    SOURCE_COUNTY_X,
    SOURCE_COUNTY_EMAIL,
    SOURCE_CITY_EMAIL,
)

SOURCE_LABELS = {
    SOURCE_COUNTY_X: "Nottinghamshire County Council @NottsCC on X",
    SOURCE_COUNTY_EMAIL: "Nottinghamshire County Council winter-service email",
    SOURCE_CITY_EMAIL: "Nottingham City Council winter-service email (proxy)",
}

COUNCIL_GRITTING_URL = "https://www.nottinghamshire.gov.uk/transport/gritting/about"
COUNCIL_EMAILME_URL = (
    "https://www.nottinghamshire.gov.uk/council-and-democracy/"
    "news-and-media/emailme/newsletter-topics"
)
X_PROFILE_URL = "https://x.com/NottsCC"
X_TIMELINE_URL = (
    "https://syndication.twitter.com/srv/timeline-profile/screen-name/NottsCC"
)
X_POLL_MINUTES = 30
