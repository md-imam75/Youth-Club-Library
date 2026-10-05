# Complete POS & Barcode System Implementation Plan

This plan outlines the architecture and step-by-step implementation to transform your existing Youth Club Library admin panel into a fully-fledged, barcode-driven Point of Sale (POS) system.

## 1. Database & Model Updates
To support barcodes and financial tracking, we need to extend the current database models (without breaking existing data).

*   **Book Model Updates:**
    *   Add `barcode` (String, unique): Stores the EAN-13 or custom barcode number.
    *   Add `low_stock_threshold` (Integer): For low stock alerts (Optional but recommended).
*   **Restock History (New Model):**
    *   `RestockLog`: Tracks every time a book is restocked (Book, Quantity Added, Date, Admin User). This provides a history rather than just blindly updating the stock number.
*   **Daily Cash Register (New Model - *Suggested*):**
    *   `CashShift`: Tracks daily cash flow (Opened At, Closed At, Opening Balance, Total Cash Sales, Closing Balance). This ensures your "Total Offline Cash" is perfectly auditable.

## 2. Barcode Generation & Printing
Before you can scan, you need physical stickers on the books.
*   **Barcode Generator:** Automatically generate an EAN-13 format barcode for every existing and new book if one doesn't exist.
*   **Printable Sticker Sheets:** A new admin page that generates a PDF of barcode stickers (e.g., standard A4 grid of 3x10 stickers or thermal printer format) containing the Barcode, Book Title, and Price. You can print these and stick them on the physical books.

## 3. The Universal "Scan Hub"
A new centralized "Scan" button on the mobile app's bottom navigation bar.
*   **Action:** Tapping it opens the camera.
*   **Flow:** Upon a successful scan, the system identifies the book and presents a modal with two distinct paths:
    1.  **Sell (Add to Bill):** Instantly adds the book to a new or active Walk-in Bill.
    2.  **Restock (Receive Inventory):** Prompts for a quantity. Submitting it adds to `Book.stock_quantity` and creates a `RestockLog`.

## 4. Enhanced Walk-in Billing (Offline Customers)
Upgrading the existing `/admin-panel/billing/make/` page.
*   **Hybrid Input:** The manual search dropdown remains intact.
*   **Scan Integration:** A prominent "Scan Book" button opens the camera. Scanning a barcode automatically adds the book as a line item. Scanning the same book twice increments the quantity by 1.
*   **Stock Deduction:** Completing the bill instantly deducts the total quantities from `Book.stock_quantity`.

## 5. Online Order Fulfillment (Verification Workflow)
Preventing manual errors when packing online orders.
*   **Order Dashboard Update:** Orders ready for delivery will have a "Pack & Deliver" button.
*   **The Workflow:**
    1.  Admin clicks "Pack & Deliver".
    2.  The screen shows the list of books in that specific order.
    3.  Admin scans the physical books they are putting in the package.
    4.  The system checks off each book as "Verified".
    5.  Only when all books are scanned and verified can the admin mark the order as "Shipped/Delivered".
    *(Note: Stock is already deducted when the customer checks out online, so this step ensures the correct physical book is given out without double-deducting stock).*

## 6. Dashboard Analytics & Financials
Enhancing the `/admin-panel/` home page with real-time POS metrics.
*   **Total Cash (Offline):** Sum of all `OfflineBill` totals paid in cash (filtered by today, this month, or all-time).
*   **Total Sales:** Combined revenue from Online `Order`s (Paid) and `OfflineBill`s.
*   **Total Amount of Books (Inventory Count):** The sum of `stock_quantity` across *all* books in the library.
*   **Total Sell Price of All Books (Inventory Value):** The sum of (`stock_quantity` * `effective_price`) for all books. Represents the total retail value of your current physical stock.
*   *Suggested Addition:* A "Low Stock Warnings" card highlighting books that need restocking.

## 7. Invoicing (Perfecting the Receipt)
*   **Thermal Printer Optimized (Optional/Suggested):** Alongside the standard A4 PDF invoice, generate a narrow HTML/PDF receipt specifically formatted for 80mm/58mm thermal POS printers (showing Logo, Bill No, Items, Total, Cash/Change, Footer).
*   **Cash & Change Tracking:** On walk-in bills, allow the admin to input "Cash Tendered" (e.g., Customer gives 1000৳ for a 750৳ bill). The invoice will explicitly show "Cash: 1000৳" and "Change: 250৳".

---

## Recommended Implementation Phases

**Phase 1: Database & Barcode Fundamentals**
*   Add barcode fields to the database.
*   Build the barcode generator and PDF sticker printing view.
*   *Outcome: You can print and attach stickers to your physical inventory.*

**Phase 2: The Core Scanning Engine & Offline POS**
*   Integrate a web-based barcode scanner (like HTML5-QRCode) that works perfectly within the Capacitor WebView.
*   Update the "Make Bill" page to accept scanned input.
*   Implement the Universal Scan Hub (Sell vs Restock logic).
*   *Outcome: You can restock and sell to offline customers using the mobile camera.*

**Phase 3: Order Fulfillment Verification**
*   Build the "Pack & Deliver" scanning UI for online orders.
*   *Outcome: Zero packing errors for online deliveries.*

**Phase 4: Analytics, Cash Register & Perfect Invoicing**
*   Update the dashboard with the new inventory valuation and cash metrics.
*   Add "Cash Tendered/Change" to the billing flow.
*   Refine the PDF generation for POS thermal receipts.
*   *Outcome: Full financial visibility and professional customer receipts.*
