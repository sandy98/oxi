#!/usr/bin/php-cgi

<?php
 //$line = trim(fgets(STDIN));
 //$stdin = fopen('php://stdin', 'r');
 //$line = trim(fgets($stdin));
 //$line = $_GET;
 echo "<style> 
    body { font-family: Arial, Helvetica, sans-serif; 
            background: #f0f0f0;
    } 
 </style>"; 
 
 echo "<style>h3 {text-align: center;}</style>";
 echo "<title>Another simple PHP proof of concept</title>";
 echo "<h1 style='text-align: center; color: #f24; font-size: 24pt; text-shadow: 3px 3px gray;'>PHP variables taken from OxiServer</h1>";
 echo "<hr/><div style='text-align: center;'>Request method: <strong>".$_SERVER['REQUEST_METHOD']."</strong></div><hr/>";
 
 echo "<h3>GET variables</h3>"; 
 foreach($_GET as $key=>$val)   
   echo "<hr/><div style='text-align: center;'>".$key.": <strong>".$val."</strong></div>";
 
echo "<h3>POST variables</h3>"; 
foreach($_POST as $key=>$val)   
  echo "<hr/><div style='text-align: center;'>".$key.": <strong>".$val."</strong></div>";

if (!empty($_FILES)) {
      // current() grabs the value of the very first element in the array
    $file = current($_FILES); 
        if ($file['error'] !== UPLOAD_ERR_OK) {
        die("Upload failed with error code: " . $file['error']);
    }
    // Now you can access properties normally without knowing the input name
    $fileName    = $file['name'];
    $fileTmpName = $file['tmp_name'];
    $fileSize    = $file['size'];
    $fileType = $file['type'];
    $mimeType = mime_content_type($fileTmpName);

    echo "<p>";
    echo "Uploaded file: ".$fileName."<br>";
    echo "Kept as: ".$fileTmpName."<br>";
    echo "File size: ".$fileSize."<br>";
    echo "File type: ".$fileType."<br>";
    echo "Mime type: ".$mimeType."<br>";
    echo "</p>";

    // 3. Handle processing and rendering based on the type
    if (str_starts_with($mimeType, 'image/')) {
        // --- IMAGE HANDLING ---
        // Convert the image data to base64 so you can easily echo it inside an HTML tag
       $fileData = file_get_contents($fileTmpName);
       $base64  = base64_encode($fileData);
        echo "<p>Here is your uploaded image:</p>";
        echo "<img src='data:{$mimeType};base64,{$base64}' alt='Uploaded Image' style='max-width:640px;' />";
    } elseif (str_starts_with($mimeType, 'text/') || $mimeType === 'application/json') {
        // --- TEXT HANDLING ---
        // Read the file as a plain string
        $textContent = file_get_contents($fileTmpName);
        echo "<p>Here is your text content:</p>";
        // htmlspecialchars prevents XSS attacks if the text file contains HTML/JS scripts
        echo "<pre>" . htmlspecialchars($textContent) . "</pre>";

    } elseif ($mimeType === 'application/pdf') {
        // --- PDF HANDLING ---
        // PDFs can't be easily echoed as raw text. 
        // You can either force the browser to view it natively by setting headers:
        header("Content-Type: application/pdf");
        header("Content-Disposition: inline; filename='" . basename($file['name']) . "'");
        readfile($fileTmpName);
        exit;

    } else {
        // --- FALLBACK / DOWNLOAD HANDLING ---
        echo "<p>Uploaded a generic file of type: <strong>" . htmlspecialchars($mimeType) . "</strong></p>";
        echo "File size: " . $file['size'] . " bytes.";
    }
}



// foreach($_REQUEST as $key=>$val)   
//    echo "<hr/><div style='text-align: center;'>".$key.": <strong>".$val."</strong></div>";

$raw_data = file_get_contents('php://input');
echo "<hr><p>Raw post data: ".$raw_data."<hr/>";
echo "Stdin contents: ".file_get_contents('php://stdin')."<hr/>";
echo "Input contents: ".file_get_contents('php://input')."<hr/></p>";

echo "<p>&nbsp;</p><p><a href='/login.html'>Back to Form</a></p>";

?>
