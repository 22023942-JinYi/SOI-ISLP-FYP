# SOI ISLP Website

## Overview
The **SOI ISLP Website** is a Flask-based web application designed to facilitate the application and management of **International Service-Learning Program (ISLP) trips**. It enables students to apply for ISLP trips, while staff members can review, approve, or decline applications. The project integrates **MySQL (Amazon RDS), AWS S3, and Amazon Cognito** for database storage, file management, and authentication.

## Features
### Main Page
- **Public Access**: Displays present and past ISLP trips.
- **Slideshow**: Showcases ISLP trip photos.
- **User Authentication**: Login and logout via **Amazon Cognito**.

### Student Features
- **Apply for ISLP Trips**:
  - Students can submit applications for available ISLP trips.
  - They can **edit and resubmit** applications before the deadline.
  - **Email confirmation** is sent upon submission.
- **View Application Status**:
  - Students can track their application status (Pending, Approved, or Declined).
  - If accepted, they gain access to **full trip details and schedules**.
- **File Uploads**:
  - Students must upload supporting documents, which are securely stored in **AWS S3**.
  
### Staff Features
- **Manage Student Applications**:
  - View all student submissions.
  - **Filter submissions** by diploma.
  - **Approve or decline applications** (individually or in bulk).
  - Students receive **automated emails** indicating approval or rejection.
- **View and Manage ISLP Trips**:
  - **Create new ISLP trips** with details and trip schedules.
  - **Edit or delete ISLP trip information**.
  - **View and manage uploaded student documents**.
  
### Administrative & Security Features
- **User Role Management**:
  - Amazon Cognito manages user groups (Students and Staff).
  - **Role-based access control** ensures students and staff have different privileges.
- **Secure File Storage**:
  - Documents, schedules, and images are stored in **AWS S3** with **KMS encryption**.
- **MySQL Database Integration**:
  - Stores ISLP details, student applications, and trip schedules using **Amazon RDS (MySQL)**.

## Tech Stack
- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **Database**: MySQL (Amazon RDS)
- **Authentication**: Amazon Cognito
- **File Storage**: AWS S3 (for student documents, trip schedules, and images)

## Contact
For questions or support, please reach out at jiinbh6@gmail.com via GitHub Issues.

