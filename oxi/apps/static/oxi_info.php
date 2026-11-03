
<?php
 //$stdin = fopen('php://stdin', 'r');
 //$line = trim(fgets($stdin));
 $line = "PHP FCGI";
 echo "<h1 style='text-align: center; color: #f24; font-size: 24pt; text-shadow: 3px 3px gray;'>PHP Info running under OxiServer</h1>";
 echo "<hr/><div style='text-align: center;'>Raw data from the server: <strong>".$line."</strong></div><hr/><p>&nbsp;</p><p>&nbsp;</p>";
 echo "<hr>";
 echo "<p style=\"text-align: center;\"><button onclick=\"location.href='/';\">Home</button> </p>";
 echo "<hr>";
 phpinfo();
 echo "<hr>";
 echo "<p style=\"text-align: center;\"><button onclick=\"location.href='/';\">Home</button> </p>";
?>
